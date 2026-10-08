from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import OfferForm, WantedPostForm
from .models import Offer, WantedPost


def show_wanted(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    wanted_posts = WantedPost.objects.select_related("requester")
    if query:
        wanted_posts = wanted_posts.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
        )
    if category in WantedPost.Category.values:
        wanted_posts = wanted_posts.filter(category=category)

    context = {
        "name": "Yelloved",
        "wanted_posts": wanted_posts,
        "query": query,
        "selected_category": category,
        "categories": WantedPost.Category.choices,
    }
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


@login_required
def create_wanted(request):
    form = WantedPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        wanted_post = form.save(commit=False)
        wanted_post.requester = request.user
        wanted_post.save()
        messages.success(request, "Wanted post berhasil dibuat.")
        return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)

    return render(
        request,
        "wanted_board/form.html",
        {"form": form, "form_title": "Buat wanted post", "name": "Yelloved"},
    )


@login_required
def edit_wanted(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk, requester=request.user)
    form = WantedPostForm(request.POST or None, instance=wanted_post)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Wanted post berhasil diperbarui.")
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
        messages.success(request, "Wanted post berhasil dihapus.")
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
        messages.error(request, "Status wanted post tidak valid.")
    else:
        wanted_post.status = status
        wanted_post.save(update_fields=["status", "updated_at"])
        messages.success(request, "Status wanted post berhasil diperbarui.")
    return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)


@login_required
@require_POST
def create_offer(request, pk):
    wanted_post = get_object_or_404(WantedPost, pk=pk)
    if wanted_post.requester == request.user:
        messages.error(request, "Kamu tidak dapat menawarkan barang ke post sendiri.")
    elif wanted_post.status != WantedPost.Status.OPEN:
        messages.error(request, "Wanted post ini sudah tidak menerima penawaran.")
    elif Offer.objects.filter(
        wanted_post=wanted_post,
        offerer=request.user,
    ).exists():
        messages.error(request, "Kamu sudah mengirim penawaran untuk post ini.")
    else:
        form = OfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.wanted_post = wanted_post
            offer.offerer = request.user
            offer.save()
            messages.success(request, "Penawaran berhasil dikirim.")
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    return redirect("wanted_board:wanted_detail", pk=wanted_post.pk)
