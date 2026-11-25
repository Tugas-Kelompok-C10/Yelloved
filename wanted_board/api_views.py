"""Wanted mobile API. Existing HTML/HTMX views keep their own routes."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException, NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .creation import issue_creation_token
from .locking import locked_wanted_post
from .models import WantedCreationReceipt, WantedPost
from .rate_limits import CreationRateLimited
from .serializers import WantedPostSerializer, WantedStatusSerializer


class WantedConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This post changed. Reload it before trying again."


class WantedPagination(PageNumberPagination):
    page_size = 12


def check_owner(request, post):
    if post.requester_id != request.user.pk:
        raise PermissionDenied("You can only manage your own wanted posts.")


def check_revision(post, revision):
    if revision != post.updated_at:
        raise WantedConflict()


@ensure_csrf_cookie
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def wanted_create_options(request):
    """Fetch once when opening a new create form; keep the token for retries."""
    return Response({
        "creation_token": issue_creation_token(request.user),
        "csrf_token": get_token(request),
        "categories": [
            {"value": value, "label": label} for value, label in WantedPost.Category.choices
        ],
    })


@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def wanted_list(request):
    """Read stored posts or create one. No external API is fetched here."""
    if request.method == "POST":
        serializer = WantedPostSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except CreationRateLimited as error:
            return Response(
                {"detail": error.message, "retry_after": error.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(error.retry_after)},
            )
        except DjangoValidationError as error:
            raise WantedConflict(error.messages) from error
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    posts = WantedPost.objects.select_related("requester").order_by("-created_at", "-pk")
    mine = request.query_params.get("mine", "false").lower()
    if mine not in ("true", "false"):
        raise ValidationError({"mine": "Use true or false."})
    if mine == "true":
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        posts = posts.filter(requester=request.user)
        selected_status = request.query_params.get("status", "")
        if selected_status:
            if selected_status not in WantedPost.Status.values:
                raise ValidationError({"status": "Choose a valid wanted status."})
            posts = posts.filter(status=selected_status)
    else:
        posts = posts.filter(status=WantedPost.Status.OPEN)

    query = request.query_params.get("search", request.query_params.get("q", "")).strip()[:70]
    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
            | Q(location__icontains=query)
            | Q(category__in=[value for value, label in WantedPost.Category.choices
                              if query.casefold() in label.casefold()])
        )
    category = request.query_params.get("category", "")
    if category:
        if category not in WantedPost.Category.values:
            raise ValidationError({"category": "Choose a valid category."})
        posts = posts.filter(category=category)
    sort = request.query_params.get("sort", "")
    if sort == "budget_asc":
        posts = posts.order_by("budget", "-created_at", "-pk")
    elif sort == "budget_desc":
        posts = posts.order_by("-budget", "-created_at", "-pk")
    elif sort:
        raise ValidationError({"sort": "Use budget_asc or budget_desc."})

    # Keep the original list response compatible. Add ?page=1 for pagination.
    if "page" in request.query_params:
        paginator = WantedPagination()
        page = paginator.paginate_queryset(posts, request)
        return paginator.get_paginated_response(WantedPostSerializer(page, many=True).data)
    return Response(WantedPostSerializer(posts, many=True).data)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def wanted_detail(request, pk):
    if request.method in ("GET", "HEAD"):
        post = get_object_or_404(WantedPost.objects.select_related("requester"), pk=pk)
        return Response(WantedPostSerializer(post).data)

    try:
        with locked_wanted_post(pk) as post:
            check_owner(request, post)
            if request.method == "DELETE":
                if post.status == WantedPost.Status.MATCHED or post.item_offers.filter(
                    matched_transaction__isnull=False,
                ).exists():
                    raise WantedConflict("This post has a transaction and cannot be deleted. Manage it from Activity.")
                post.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)

            if post.status != WantedPost.Status.OPEN:
                raise WantedConflict("Only open wanted posts can be edited.")
            serializer = WantedPostSerializer(
                post, data=request.data, partial=request.method == "PATCH",
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            check_revision(post, serializer.validated_data["revision"])
            serializer.save()
            return Response(serializer.data)
    except Http404:
        if request.method == "DELETE" and WantedCreationReceipt.objects.filter(
            pk=pk, requester=request.user, deleted_at__isnull=False,
        ).exists():
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def wanted_status(request, pk):
    """Owner status changes; matching/completion stays in the transaction flow."""
    with locked_wanted_post(pk) as post:
        check_owner(request, post)
        serializer = WantedStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check_revision(post, serializer.validated_data["revision"])
        new_status = serializer.validated_data["status"]
        if new_status == WantedPost.Status.MATCHED or post.status == WantedPost.Status.MATCHED:
            raise WantedConflict("Manage this match through its transaction in Activity.")
        if post.item_offers.filter(
            matched_transaction__isnull=False,
            matched_transaction__transaction_status="completed",
        ).exists():
            raise WantedConflict("A completed transaction keeps this wanted post fulfilled.")
        post.status = new_status
        post.save(update_fields=["status", "updated_at"])
        return Response(WantedPostSerializer(post).data)
