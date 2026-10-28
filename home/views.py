from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from items.models import Item
from wanted_board.models import WantedPost
from wanted_board.sample_data import SAMPLE_WANTED_POSTS
from wanted_board.views import _wanted_cards, _sample_posts_for


PREVIEW_ITEMS = (
    {"title": "Brown wired headphones", "condition": "Good", "price": "Rp 85.000", "location": "Kukusan, Depok"},
    {"title": "Used HP laptop", "condition": "Great", "price": "Rp 2.500.000", "location": "Pondok Cina, Depok"},
    {"title": "Dorm desk monitor", "condition": "Very good", "price": "Rp 650.000", "location": "Around UI, Depok"},
    {"title": "Standing fan", "condition": "Good", "price": "Free", "location": "Depok"},
    {"title": "Everyday campus backpack", "condition": "Great", "price": "Rp 95.000", "location": "Kukusan"},
    {"title": "A book for next semester", "condition": "Good", "price": "Rp 60.000", "location": "UI Library"},
    {"title": "Compact study lamp", "condition": "Very good", "price": "Rp 75.000", "location": "Pondok Cina"},
    {"title": "Comfy desk chair", "condition": "Good", "price": "Rp 180.000", "location": "Margonda"},
    {"title": "Stainless steel water bottle", "condition": "Great", "price": "Rp 45.000", "location": "Kutek"},
    {"title": "Small rice cooker", "condition": "Good", "price": "Rp 120.000", "location": "Beji, Depok"},
    {"title": "Canvas campus tote", "condition": "Very good", "price": "Rp 35.000", "location": "Fasilkom UI"},
    {"title": "Adjustable laptop stand", "condition": "Great", "price": "Rp 70.000", "location": "Pondok Cina"},
)


def show_main(request):
    posts = list(WantedPost.objects.select_related("requester").order_by("-created_at", "-pk")[:4])
    context = {
        "name": "Yelloved",
        "heart_count": request.session.get("landing_hearts", 0),
        "preview_items": PREVIEW_ITEMS,
        "wanted_cards": _wanted_cards(posts, SAMPLE_WANTED_POSTS[:4 - len(posts)],
                                      user_id=request.user.pk if request.user.is_authenticated else None),
    }
    return render(request, "index.html", context)


def search_catalogue(request):
    """The navbar searches both catalogues without changing their existing filters."""
    query = request.GET.get("q", "").strip()
    if not query:
        return redirect("items:explore_items")
    items = Item.objects.filter(status=Item.Status.AVAILABLE).filter(
        Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query)
    ).order_by("-created_at", "-pk")[:12]
    posts = list(WantedPost.objects.select_related("requester").filter(
        Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query)
    ).order_by("-created_at", "-pk")[:12])
    return render(request, "home/search.html", {
        "name": "Yelloved", "navbar_query": query, "query": query, "items": items,
        "search_wanted": _wanted_cards(posts, _sample_posts_for(query, "")[:12 - len(posts)]),
    })


@require_POST
def send_love(request):
    """A playful, session-scoped interaction; no account or global metric required."""
    count = request.session.get("landing_hearts", 0) + 1
    request.session["landing_hearts"] = count
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"count": count})
    return redirect("show_main")
