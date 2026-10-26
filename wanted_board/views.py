from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import OfferForm, WantedPostForm
from .models import Offer, WantedPost
from .sample_data import SAMPLE_WANTED_POSTS


def _sample_posts_for(query, category, condition, listing_type):
    sample_posts = SAMPLE_WANTED_POSTS
    if query:
        normalized_query = query.casefold()
        if normalized_query in WantedPost.ListingType.values:
            sample_posts = tuple(
                post
                for post in sample_posts
                if post["listing_type"] == normalized_query
            )
        else:
            sample_posts = tuple(
                post
                for post in sample_posts
                if normalized_query
                in " ".join(
                    (
                        post["title"],
                        post["description"],
                        post["location"],
                        post["poster"],
                        post["listing_type_label"],
                        post["category_label"],
                        post["condition_label"],
                        post["source_category"],
                    )
                ).casefold()
            )
    if category in WantedPost.Category.values:
        sample_posts = tuple(
            post for post in sample_posts if post["category"] == category
        )
    if condition in WantedPost.Condition.values:
        sample_posts = tuple(
            post for post in sample_posts if post["condition"] == condition
        )
    if listing_type in WantedPost.ListingType.values:
        sample_posts = tuple(
            post
            for post in sample_posts
            if post["listing_type"] == listing_type
        )
    return sample_posts


def _wanted_cards(wanted_posts, sample_posts):
    cards = [
        {
            "title": post.title,
            "image_url": post.image.url if post.image else "",
            "description": post.description,
            "category_label": post.get_category_display(),
            "listing_type_label": post.get_listing_type_display(),
            "condition_label": post.get_preferred_condition_display(),
            "budget": post.budget,
            "location": post.location or "Around UI",
            "poster": post.requester.username,
            "status": post.status,
            "status_label": post.get_status_display(),
            "detail_url": reverse("wanted_board:wanted_detail", args=[post.pk]),
            "is_sample": False,
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
        }
        for post in sample_posts
    )
    return cards


def _board_context(request, creation_form=None, open_create_modal=False):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    condition = request.GET.get("condition", "").strip()
    listing_type = request.GET.get("listing_type", "").strip()

    wanted_posts = WantedPost.objects.select_related("requester")
    if query:
        normalized_query = query.casefold()
        if normalized_query in WantedPost.ListingType.values:
            wanted_posts = wanted_posts.filter(listing_type=normalized_query)
        else:
            wanted_posts = wanted_posts.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(location__icontains=query)
                | Q(listing_type__icontains=query)
            )
    if category in WantedPost.Category.values:
        wanted_posts = wanted_posts.filter(category=category)
    if condition in WantedPost.Condition.values:
        wanted_posts = wanted_posts.filter(preferred_condition=condition)
    if listing_type in WantedPost.ListingType.values:
        wanted_posts = wanted_posts.filter(listing_type=listing_type)

    sample_posts = _sample_posts_for(query, category, condition, listing_type)
    wanted_cards = _wanted_cards(wanted_posts, sample_posts)

    return {
        "name": "Yelloved",
        "wanted_posts": wanted_posts,
        "query": query,
        "selected_category": category,
        "selected_condition": condition,
        "selected_listing_type": listing_type,
        "categories": WantedPost.Category.choices,
        "conditions": WantedPost.Condition.choices,
        "listing_types": WantedPost.ListingType.choices,
        "sample_posts": sample_posts,
        "wanted_cards": wanted_cards,
        "total_count": len(wanted_cards),
        "creation_form": (
            creation_form if creation_form is not None else WantedPostForm()
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
                "selected_condition": context["selected_condition"],
                "selected_listing_type": context["selected_listing_type"],
            }
        )
    return render(request, "wanted_post.html", context)


def wanted_detail(request, pk):
    wanted_post = get_object_or_404(
        WantedPost.objects.select_related("requester").prefetch_related(
            "offers__offerer"
        ),
        pk=pk,
    )
    has_offered = (
        request.user.is_authenticated
        and wanted_post.offers.filter(offerer=request.user).exists()
    )
    context = {
        "name": "Yelloved",
        "wanted_post": wanted_post,
        "offer_form": OfferForm(),
        "has_offered": has_offered,
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


@login_required
def create_wanted(request):
    if request.method == "GET":
        return redirect(f"{reverse('wanted_board:show_wanted')}?create=1")

    form = WantedPostForm(request.POST, request.FILES)
    if request.method == "POST" and form.is_valid():
        wanted_post = form.save(commit=False)
        wanted_post.requester = request.user
        wanted_post.save()
        messages.success(request, "Your wanted post has been created.")
        return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)

    context = _board_context(
        request,
        creation_form=form,
        open_create_modal=True,
    )
    return render(request, "wanted_post.html", context)


@login_required
def edit_wanted(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
    form = WantedPostForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=wanted_post,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your wanted post has been updated.")
        return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)

    return render(
        request,
        "wanted_board/form.html",
        {
            "form": form,
            "form_title": "Edit wanted post",
            "wanted_post": wanted_post,
            "name": "Yelloved",
        },
    )


@login_required
def delete_wanted(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
    if request.method == "POST":
        wanted_post.delete()
        messages.success(request, "Your wanted post has been deleted.")
        return redirect("wanted_board:show_wanted")
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", "POST"])

    return render(
        request,
        "wanted_board/confirm_delete.html",
        {"wanted_post": wanted_post, "name": "Yelloved"},
    )


@login_required
@require_POST
def update_status(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
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
def create_offer(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk)
    if wanted_post.requester == request.user:
        messages.error(request, "You cannot make an offer on your own post.")
    elif wanted_post.status != WantedPost.Status.OPEN:
        messages.error(request, "This wanted post is no longer accepting offers.")
    elif Offer.objects.filter(
        wanted_post=wanted_post,
        offerer=request.user,
    ).exists():
        messages.error(request, "You have already made an offer on this post.")
    else:
        form = OfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.wanted_post = wanted_post
            offer.offerer = request.user
            offer.save()
            messages.success(request, "Your offer has been sent.")
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)
