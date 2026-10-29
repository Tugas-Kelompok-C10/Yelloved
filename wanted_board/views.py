from urllib.parse import urlencode
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .creation import creation_uid, issue_creation_token
from .forms import OfferForm, WantedCreateForm, WantedEditForm
from .locking import locked_wanted_post
from .models import Offer, WantedPost
from .rate_limits import CreationRateLimited, create_with_quota
from .sample_data import SAMPLE_WANTED_POSTS


def _sample_posts_for(query, category):
    sample_posts = SAMPLE_WANTED_POSTS
    if query:
        normalized_query = query.casefold()
        sample_posts = tuple(
            post
            for post in sample_posts
            if normalized_query
            in " ".join(
                (
                    post["title"],
                    post["description"],
                    post["location"],
                    post["category_label"],
                )
            ).casefold()
        )
    if category in WantedPost.Category.values:
        sample_posts = tuple(
            post for post in sample_posts if post["category"] == category
        )
    return sample_posts


def _wanted_cards(wanted_posts, sample_posts, user_id=None):
    cards = [
        {
            "title": post.title,
            "description": post.description,
            "category_label": post.get_category_display(),
            "budget": post.budget,
            "location": post.location or "Around UI",
            "poster": post.requester.username,
            "status": post.status,
            "status_label": post.get_status_display(),
            "detail_url": reverse("wanted_board:wanted_detail", args=[post.pk]),
            "is_sample": False,
            "is_owner": post.requester_id == user_id,
            "chat_url": reverse("chat:with_user", args=[post.requester_id]),
        }
        for post in wanted_posts
    ]
    cards.extend(
        {
            **post,
            "detail_url": reverse(
                "wanted_board:sample_wanted_detail",
                args=[post["slug"]],
            ),
            "is_sample": True,
            "chat_url": reverse("chat:inbox"),
        }
        for post in sample_posts
    )
    return cards


def _page_numbers(current, total):
    """Show at most six page numbers, keeping the first, current and last pages."""
    if total <= 6:
        return list(range(1, total + 1))
    start = max(2, min(current - 1, total - 4))
    numbers = [1, *range(start, start + 4), total]
    result = []
    for number in numbers:
        if result and number - result[-1] > 1:
            result.append(Paginator.ELLIPSIS)
        result.append(number)
    return result


def _wanted_page(wanted_posts, sample_posts, number, per_page=12, user_id=None):
    """Slice database matches before building cards, then fill with demo posts."""
    post_count = wanted_posts.count()
    paginator = Paginator(range(post_count + len(sample_posts)), per_page)
    page = paginator.get_page(number)
    start = (page.number - 1) * per_page
    end = start + per_page
    page.object_list = _wanted_cards(
        wanted_posts[min(start, post_count):min(end, post_count)],
        sample_posts[max(0, start - post_count):max(0, end - post_count)],
        user_id=user_id,
    )
    return page


def _board_context(request, creation_form=None, open_create_modal=False):
    query = request.GET.get("q", "").strip()[:70]
    category = request.GET.get("category", "").strip()

    wanted_posts = WantedPost.objects.filter(status=WantedPost.Status.OPEN).select_related("requester").order_by("-created_at", "-pk")
    if query:
        wanted_posts = wanted_posts.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
            | Q(category__in=[value for value, label in WantedPost.Category.choices if query.casefold() in label.casefold()])
        )
    if category in WantedPost.Category.values:
        wanted_posts = wanted_posts.filter(category=category)

    sample_posts = _sample_posts_for(query, category)
    # Paginate real posts first, then samples, without loading all database rows.
    page = _wanted_page(
        wanted_posts, sample_posts, request.GET.get("page"),
        user_id=request.user.pk if request.user.is_authenticated else None,
    )
    paginator = page.paginator
    wanted_cards = page.object_list

    def page_url(number):
        params = {"page": number}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        return f"{reverse('wanted_board:show_wanted')}?{urlencode(params)}"

    return {
        "name": "Yelloved",
        "wanted_posts": wanted_posts,
        "query": query,
        "selected_category": category,
        "categories": WantedPost.Category.choices,
        "sample_posts": sample_posts,
        "wanted_cards": wanted_cards,
        "total_count": paginator.count,
        "page_obj": page,
        "pagination_links": [
            {"number": number, "url": page_url(number) if number != paginator.ELLIPSIS else None}
            for number in _page_numbers(page.number, paginator.num_pages)
        ],
        "previous_page_url": page_url(page.previous_page_number()) if page.has_previous() else None,
        "next_page_url": page_url(page.next_page_number()) if page.has_next() else None,
        "creation_form": (
            creation_form if creation_form is not None else WantedCreateForm(
                initial={"creation_token": issue_creation_token(request.user),
                         "title": request.GET.get("title", "")[:50]}, user=request.user,
            )
        ),
        "open_create_modal": open_create_modal,
    }


def show_wanted(request):
    context = _board_context(
        request,
        open_create_modal=request.GET.get("create") == "1",
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        total_count = context["total_count"]
        return JsonResponse(
            {
                "html": render_to_string(
                    "wanted_board/_card_grid.html",
                    context,
                    request=request,
                ),
                "result_label": (
                    f"{total_count} request"
                    f"{'s' if total_count != 1 else ''} found"
                ),
                "selected_category": context["selected_category"],
                "page_number": context["page_obj"].number,
                "pagination_html": render_to_string(
                    "wanted_board/_pagination.html", context, request=request,
                ),
            }
        )
    return render(request, "wanted_post.html", context)


def wanted_detail(request, pk):
    wanted_post = get_object_or_404(
        WantedPost.objects.select_related(
            "requester", "requester__account_profile"
        ),
        pk=pk,
    )
    context = {
        "name": "Yelloved",
        "wanted_post": wanted_post,
        "edit_form": (
            WantedEditForm(instance=wanted_post)
            if request.user == wanted_post.requester
            else None
        ),
        "open_edit_modal": (
            request.user == wanted_post.requester
            and request.GET.get("edit") == "1"
        ),
        "open_delete_modal": (
            request.user == wanted_post.requester
            and request.GET.get("delete") == "1"
        ),
    }
    return render(request, "wanted_board/detail.html", context)


def sample_wanted_detail(request, slug):
    sample_post = next(
        (post for post in SAMPLE_WANTED_POSTS if post["slug"] == slug),
        None,
    )
    if sample_post is None:
        raise Http404("Sample wanted post not found")

    return render(
        request,
        "wanted_board/sample_detail.html",
        {"name": "Yelloved", "wanted_post": sample_post},
    )


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _clear_access_errors(view):
    """Keep normal 404s, but let Wanted AJAX forms explain rejected access."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Http404:
            if not _is_ajax(request):
                raise
            return JsonResponse({"message": (
                "This wanted post is no longer available, or you do not have permission "
                "to change it. Return to the board and refresh before trying again."
            )}, status=404)
    return wrapped


def _saved_response(request, wanted_post, message):
    url = reverse("wanted_board:wanted_detail", args=[wanted_post.pk])
    if _is_ajax(request):
        data = {"redirect_url": url, "uid": str(wanted_post.pk), "message": message,
                "board_url": reverse("wanted_board:show_wanted")}
        if request.resolver_match.url_name == "edit_wanted":
            wanted_post.refresh_from_db()
            data.update(title=wanted_post.title, revision=wanted_post.updated_at.isoformat(),
                        detail_html=render_to_string("wanted_board/_detail_body.html",
                                                    {"wanted_post": wanted_post}, request=request))
        return JsonResponse(data)
    messages.success(request, message)
    return redirect(url)


def _form_errors_response(form):
    return JsonResponse({"errors": form.errors.get_json_data()}, status=422)


@login_required
def create_wanted(request):
    if request.method == "GET":
        return redirect(f"{reverse('wanted_board:show_wanted')}?create=1")
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    form = WantedCreateForm(request.POST, user=request.user)
    rate_error = None
    try:
        uid = creation_uid(request.POST.get("creation_token", ""), request.user)
    except ValidationError as error:
        form.is_valid()
        form.add_error(None, error)
    else:
        existing_post = WantedPost.objects.filter(pk=uid, requester=request.user).first()
        if existing_post:
            return _saved_response(request, existing_post, "Your wanted post has been created.")
        if form.is_valid():
            defaults = {
                key: value for key, value in form.cleaned_data.items()
                if key != "creation_token"
            }
            try:
                wanted_post = create_with_quota(request.user, uid, defaults)
            except CreationRateLimited as error:
                rate_error = error
                form.add_error(None, error.message)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return _saved_response(request, wanted_post, "Your wanted post has been created.")

    if _is_ajax(request):
        if rate_error:
            response = JsonResponse({"message": rate_error.message,
                                     "errors": form.errors.get_json_data(),
                                     "retry_after": rate_error.retry_after}, status=429)
            response["Retry-After"] = str(rate_error.retry_after)
            return response
        return _form_errors_response(form)

    context = _board_context(
        request,
        creation_form=form,
        open_create_modal=True,
    )
    response = render(request, "wanted_post.html", context, status=429 if rate_error else 200)
    if rate_error:
        response["Retry-After"] = str(rate_error.retry_after)
    return response


@login_required
@_clear_access_errors
def edit_wanted(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
    if request.method == "GET":
        return redirect(
            f"{reverse('wanted_board:wanted_detail', args=[wanted_post.pk])}?edit=1"
        )
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    form = WantedEditForm(
        request.POST,
        instance=wanted_post,
    )
    if form.is_valid():
        # Compare and write atomically so a second tab cannot overwrite newer edits.
        if form.cleaned_data["revision"] == wanted_post.updated_at.isoformat():
            changes = {field: form.cleaned_data[field] for field in form.Meta.fields}
            changed = WantedPost.objects.filter(pk=pk, requester=request.user,
                                                updated_at=wanted_post.updated_at).update(
                **changes, updated_at=timezone.now())
            if changed:
                return _saved_response(request, wanted_post, "Your wanted post has been updated.")
        form.add_error(None, "This post changed in another tab. Your edits are kept here. Copy them, then reload to review the latest version before saving.")

    if _is_ajax(request):
        return _form_errors_response(form)

    # ModelForm validation mutates its instance even when other fields fail.
    # Render the persisted post in the detail behind the bound edit modal.
    wanted_post.refresh_from_db()

    return render(
        request,
        "wanted_board/detail.html",
        {
            "edit_form": form,
            "open_edit_modal": True,
            "open_delete_modal": False,
            "wanted_post": wanted_post,
            "name": "Yelloved",
        },
    )


@login_required
@_clear_access_errors
def delete_wanted(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
    if request.method == "POST":
        wanted_post.delete()
        if _is_ajax(request):
            return JsonResponse({"message": "Your wanted post has been deleted.",
                                 "board_url": reverse("wanted_board:show_wanted")})
        messages.success(request, "Your wanted post has been deleted.")
        return redirect("wanted_board:show_wanted")
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", "POST"])
    return redirect(
        f"{reverse('wanted_board:wanted_detail', args=[wanted_post.pk])}?delete=1"
    )


@login_required
@require_POST
@_clear_access_errors
def update_status(request, pk):
    with locked_wanted_post(pk, requester=request.user) as wanted_post:
        status = request.POST.get("status")
        if status not in WantedPost.Status.values:
            messages.error(request, "That wanted post status is not valid.")
        else:
            wanted_post.status = status
            wanted_post.save(update_fields=["status", "updated_at"])
            messages.success(request, "The wanted post status has been updated.")
    return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)


@login_required
@require_POST
@_clear_access_errors
def create_offer(request, pk):
    # Status inspection and insertion share one lock/transaction. Closing a post
    # must finish before this check, or wait until this offer has committed.
    with locked_wanted_post(pk) as wanted_post:
        if wanted_post.requester == request.user:
            messages.error(request, "You cannot make an offer on your own post.")
        elif wanted_post.status != WantedPost.Status.OPEN:
            messages.error(request, "This wanted post is no longer accepting offers.")
        else:
            form = OfferForm(request.POST)
            if form.is_valid():
                # Keep the database constraint as a second guard against duplicates.
                _, created = Offer.objects.get_or_create(
                    wanted_post=wanted_post,
                    offerer=request.user,
                    defaults={"offered_price": form.cleaned_data["offered_price"], "message": ""},
                )
                if created:
                    messages.success(request, "Your offer has been sent.")
                else:
                    messages.error(request, "You have already made an offer on this post.")
            else:
                for errors in form.errors.values():
                    for error in errors:
                        messages.error(request, error)

    return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)
