from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.template.loader import render_to_string
from urllib.parse import urlencode
from django.core.paginator import Paginator

from items.models import Item
from wanted_board.models import WantedPost
from wanted_board.sample_data import SAMPLE_WANTED_POSTS
from wanted_board.views import _wanted_cards, _sample_posts_for, _wanted_page


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
    posts = list(WantedPost.objects.filter(status=WantedPost.Status.OPEN).select_related("requester").order_by("-created_at", "-pk")[:4])
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
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if len(query) > 100:
        message = "Please keep your search within 100 characters."
        if is_ajax:
            return JsonResponse({"html": f'<p role="alert">{message}</p>', "error": message}, status=400)
        return render(request, "home/search_error.html", {"search_error": message}, status=400)
    if not query:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"html": ""})
        return redirect("items:explore_items")
    items = Item.objects.filter(status=Item.Status.AVAILABLE).filter(
        Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query)
        | Q(category__in=[value for value, label in Item.Category.choices if query.casefold() in label.casefold()])
    ).order_by("-created_at", "-pk")
    posts = WantedPost.objects.filter(status=WantedPost.Status.OPEN).select_related("requester").filter(
        Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query)
        | Q(category__in=[value for value, label in WantedPost.Category.choices if query.casefold() in label.casefold()])
    ).order_by("-created_at", "-pk")
    # Tabs share one query and keep the two result types in separate sections.
    selected_type = request.GET.get("type", "all")
    if selected_type not in {"all", "items", "wanted"}:
        selected_type = "all"
    wanted_page = _wanted_page(
        posts, _sample_posts_for(query, ""),
        request.GET.get("page") if selected_type == "wanted" and not is_ajax else 1,
        per_page=12 if selected_type == "wanted" and not is_ajax else 4,
        user_id=request.user.pk if request.user.is_authenticated else None,
    )
    wanted_cards = wanted_page.object_list
    item_count, wanted_count = items.count(), wanted_page.paginator.count
    page = None
    if is_ajax:
        displayed_items, displayed_wanted = items[:4], wanted_cards
    elif selected_type == "items":
        page = Paginator(items, 12).get_page(request.GET.get("page"))
        displayed_items, displayed_wanted = list(page), []
    elif selected_type == "wanted":
        page = wanted_page
        displayed_items, displayed_wanted = [], list(page)
    else:
        displayed_items, displayed_wanted = list(items[:4]), wanted_cards[:4]

    def tab_url(result_type, number=None):
        params = {"q": query, "type": result_type}
        if number is not None:
            params["page"] = number
        return reverse("search_catalogue") + "?" + urlencode(params)

    context = {
        "name": "Yelloved", "navbar_query": query, "query": query, "items": displayed_items,
        "search_wanted": displayed_wanted,
        "selected_type": selected_type, "item_count": item_count, "wanted_count": wanted_count,
        "all_url": tab_url("all"), "items_url": tab_url("items"), "wanted_url": tab_url("wanted"),
        "page_obj": page,
        "previous_url": tab_url(selected_type, page.previous_page_number()) if page and page.has_previous() else None,
        "next_url": tab_url(selected_type, page.next_page_number()) if page and page.has_next() else None,
        "pin_url": reverse("wanted_board:show_wanted") + "?" + urlencode({"create": "1", "title": query[:50]}),
    }
    if not request.user.is_authenticated:
        context["pin_url"] = reverse("login") + "?" + urlencode({"next": context["pin_url"]})
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Navbar suggestions always preview both catalogues, independent of the page tab.
        context["items"], context["search_wanted"] = items[:4], wanted_cards[:4]
        return JsonResponse({"html": render_to_string("home/_search_suggestions.html", context, request=request)})
    return render(request, "home/search.html", context)


@require_POST
def send_love(request):
    """A playful, session-scoped interaction; no account or global metric required."""
    count = request.session.get("landing_hearts", 0) + 1
    request.session["landing_hearts"] = count
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"count": count})
    return redirect("show_main")
