"""Adapt the first 30 DummyJSON products into Wanted Board sample posts."""

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from django.utils.text import slugify


DUMMYJSON_PRODUCTS_URL = "https://dummyjson.com/products?limit=30"
USD_TO_IDR = Decimal("16000")
SNAPSHOT_PATH = Path(__file__).with_name("dummyjson_products.json")

LOCATIONS = (
    "Fasilkom UI",
    "UI Library",
    "Kukusan",
    "Pondok Cina",
    "Margonda",
    "Beji",
)

FASHION_CATEGORIES = {
    "beauty",
    "fragrances",
    "mens-shirts",
    "mens-shoes",
    "tops",
    "womens-bags",
    "womens-dresses",
    "womens-jewellery",
    "womens-shoes",
}
BOOK_CATEGORIES = {"books"}
ELECTRONICS_CATEGORIES = {
    "laptops",
    "mobile-accessories",
    "smartphones",
    "tablets",
}
HOME_CATEGORIES = {
    "furniture",
    "home-decoration",
    "kitchen-accessories",
}


def _wanted_category(source_category):
    if source_category in FASHION_CATEGORIES:
        return "fashion", "Fashion"
    if source_category in BOOK_CATEGORIES:
        return "books", "Books & Study"
    if source_category in ELECTRONICS_CATEGORIES:
        return "electronics", "Electronics"
    if source_category in HOME_CATEGORIES:
        return "home", "Home & Living"
    return "other", "Other"


def _wanted_condition(rating):
    rating = Decimal(str(rating or 0))
    if rating >= Decimal("4.5"):
        return "new", "New"
    if rating >= Decimal("3.5"):
        return "lightly_used", "Lightly used"
    return "well_used", "Well used"


def _rupiah_budget(price):
    return (
        Decimal(str(price)) * USD_TO_IDR / Decimal("1000")
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("1000")


def _posted_on(value):
    try:
        created_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return "DummyJSON sample"
    return f"{created_at.day} {created_at:%B %Y}"


def _poster_details(product):
    poster = product.get("brand") or "Yelloved Community"
    initials = "".join(word[0] for word in poster.split()[:2]).upper()
    return poster, initials or "YC"


def _adapt_product(product, index):
    category, category_label = _wanted_category(product.get("category", ""))
    condition, condition_label = _wanted_condition(product.get("rating"))
    price = Decimal(str(product.get("price") or 0))
    is_free = price < Decimal("3")
    poster, poster_initials = _poster_details(product)
    product_id = int(product["id"])

    return {
        "source": "DummyJSON",
        "source_id": product_id,
        "slug": f"dummyjson-{product_id}-{slugify(product['title'])}",
        "title": product["title"],
        "description": product["description"],
        "category": category,
        "category_label": category_label,
        "listing_type": "free" if is_free else "sell",
        "listing_type_label": "Free" if is_free else "Sell",
        "condition": condition,
        "condition_label": condition_label,
        "budget": None if is_free else _rupiah_budget(price),
        "location": LOCATIONS[index % len(LOCATIONS)],
        "poster": poster,
        "poster_initials": poster_initials,
        "status": "open",
        "status_label": "Open",
        "posted_on": _posted_on(product.get("createdAt")),
        "image_url": product.get("thumbnail", ""),
        "rating": product.get("rating"),
        "stock": product.get("stock"),
        "source_category": product.get("category", ""),
    }


@lru_cache(maxsize=1)
def get_sample_wanted_posts():
    """Return a deterministic 30-product snapshot from DummyJSON."""
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    products = payload.get("products", [])
    if len(products) != 30:
        raise ValueError("The DummyJSON Wanted Board snapshot must contain 30 products.")
    return tuple(
        _adapt_product(product, index)
        for index, product in enumerate(products)
    )


SAMPLE_WANTED_POSTS = get_sample_wanted_posts()
