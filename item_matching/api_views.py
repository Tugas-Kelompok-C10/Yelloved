"""Item matching mobile API. Existing HTML views keep their own routes."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from items.models import Item
from wanted_board.models import WantedPost

from . import services
from .forms import ItemOfferForm, ItemRequestForm
from .matching import suggest_items_for_wanted, suggest_wanted_for_item
from .models import ItemOffer, ItemRequest
from .serializers import ItemOfferSerializer, ItemRequestSerializer, MatchSerializer
from .services import MatchingError
from .tabs import TAB_KEYS

AUTH = [SessionAuthentication, TokenAuthentication]


class MatchingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action is not allowed right now."


def _raise_form_errors(form):
    errors = {("non_field_errors" if name == "__all__" else name): list(messages)
              for name, messages in form.errors.items()}
    raise ValidationError(errors)


@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def dashboard(request):
    """?tab=incoming|sent|offers_received|offers_sent (default incoming)."""
    tab = request.query_params.get("tab", "incoming")
    if tab not in TAB_KEYS:
        raise ValidationError({"tab": f"Use one of: {', '.join(TAB_KEYS)}."})
    user = request.user
    requests_qs = ItemRequest.objects.select_related("item", "item__owner", "requester")
    offers_qs = ItemOffer.objects.select_related(
        "item", "wanted_post", "wanted_post__requester", "offerer")
    context = {"request": request}
    if tab == "incoming":
        data = ItemRequestSerializer(requests_qs.filter(item__owner=user), many=True, context=context)
    elif tab == "sent":
        data = ItemRequestSerializer(requests_qs.filter(requester=user), many=True, context=context)
    elif tab == "offers_received":
        data = ItemOfferSerializer(offers_qs.filter(wanted_post__requester=user), many=True, context=context)
    else:
        data = ItemOfferSerializer(offers_qs.filter(offerer=user), many=True, context=context)
    return Response({"tab": tab, "results": data.data})


@api_view(["POST"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def request_create(request, item_id):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_id)
    if item.owner_id is None or item.source != "user":
        raise ValidationError({"detail": "Inspiration catalog items cannot be requested."})
    if item.owner_id == request.user.pk:
        raise ValidationError({"detail": "You cannot request your own item."})
    if item.status != Item.Status.AVAILABLE:
        raise MatchingConflict("This item is no longer available.")
    form = ItemRequestForm(request.data, item=item, user=request.user)
    if not form.is_valid():
        _raise_form_errors(form)
    obj = form.save()
    return Response(ItemRequestSerializer(obj, context={"request": request}).data,
                    status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def offer_create(request, wanted_id):
    post = get_object_or_404(WantedPost.objects.select_related("requester"), pk=wanted_id)
    if post.requester_id == request.user.pk:
        raise ValidationError({"detail": "Cannot offer on your own post."})
    if post.status != WantedPost.Status.OPEN:
        raise MatchingConflict("This wanted post is no longer accepting offers.")
    form = ItemOfferForm(request.data, wanted_post=post, user=request.user)
    if not form.is_valid():
        _raise_form_errors(form)
    obj = form.save()
    return Response(ItemOfferSerializer(obj, context={"request": request}).data,
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def wanted_suggestions(request, pk):
    post = get_object_or_404(WantedPost.objects.select_related("requester"), pk=pk)
    if post.requester_id != request.user.pk:
        raise PermissionDenied("Only the wanted post owner can view these suggestions.")
    return Response(MatchSerializer(suggest_items_for_wanted(post), many=True).data)


@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def item_suggestions(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.owner_id != request.user.pk:
        raise PermissionDenied("Only the item owner can view these suggestions.")
    return Response(MatchSerializer(suggest_wanted_for_item(item), many=True).data)


def _transition(request, model, serializer_class, func, pk):
    get_object_or_404(model, pk=pk)
    try:
        obj = func(pk, request.user)
    except MatchingError as error:
        raise MatchingConflict(str(error)) from error
    return Response(serializer_class(obj, context={"request": request}).data)


def _action(model, serializer_class, func):
    @api_view(["POST"])
    @authentication_classes(AUTH)
    @permission_classes([IsAuthenticated])
    def view(request, pk):
        return _transition(request, model, serializer_class, func, pk)
    view.__name__ = func.__name__
    return view


request_accept = _action(ItemRequest, ItemRequestSerializer, services.accept_request)
request_reject = _action(ItemRequest, ItemRequestSerializer, services.reject_request)
request_cancel = _action(ItemRequest, ItemRequestSerializer, services.cancel_request)
offer_accept = _action(ItemOffer, ItemOfferSerializer, services.accept_offer)
offer_reject = _action(ItemOffer, ItemOfferSerializer, services.reject_offer)
offer_withdraw = _action(ItemOffer, ItemOfferSerializer, services.withdraw_offer)
