"""Adapt the first 30 DummyJSON products into Wanted Board sample posts."""

import json
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

import requests
from django.core.cache import caches
from django.utils.text import slugify


DUMMYJSON_PRODUCTS_URL = "https://dummyjson.com/products?limit=30"
USD_TO_IDR = Decimal("16000")
SNAPSHOT_PATH = Path(__file__).with_name("dummyjson_products.json")
CACHE_KEY = "dummyjson:wanted:v1:fresh"
STALE_KEY = "dummyjson:wanted:v1:last-good"
CACHE_SECONDS = 600
FALLBACK_SECONDS = 60
STALE_SECONDS = 86400
logger = logging.getLogger(__name__)

LOCATIONS = (
    "Fasilkom UI",
    "UI Library",
    "Kukusan",
    "Pondok Cina",
    "Margonda",
    "Beji",
)

FASHION_CATEGORIES = {
    "fragrances",
    "mens-shirts",
    "mens-shoes",
    "tops",
    "womens-bags",
    "womens-dresses",
    "womens-jewellery",
    "womens-shoes",
}
SKINCARE_CATEGORIES = {"beauty", "skin-care"}
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
}
KITCHEN_HOUSEWARE_CATEGORIES = {"kitchen-accessories", "groceries"}


def _wanted_category(source_category):
    if source_category in SKINCARE_CATEGORIES:
        return "skincare", "Skincare"
    if source_category in KITCHEN_HOUSEWARE_CATEGORIES:
        return "kitchen_houseware", "Kitchen & Houseware"
    if source_category in FASHION_CATEGORIES:
        return "fashion", "Fashion"
    if source_category in BOOK_CATEGORIES:
        return "books", "Books & Study"
    if source_category in ELECTRONICS_CATEGORIES:
        return "electronics", "Electronics"
    if source_category in HOME_CATEGORIES:
        return "home", "Home & Living"
    return "other", "Other"


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
    price = Decimal(str(product.get("price") or 0))
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
        "budget": _rupiah_budget(price),
        "location": LOCATIONS[index % len(LOCATIONS)],
        "poster": poster,
        "poster_initials": poster_initials,
        "status": "open",
        "status_label": "Open",
        "posted_on": _posted_on(product.get("createdAt") or (product.get("meta") or {}).get("createdAt")),
        "rating": product.get("rating"),
        "stock": product.get("stock"),
        "source_category": product.get("category", ""),
    }


@lru_cache(maxsize=1)
def _snapshot_posts():
    """The bundled snapshot remains available without a network connection."""
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    products = payload.get("products", [])
    if len(products) != 30:
        raise ValueError("The DummyJSON Wanted Board snapshot must contain 30 products.")
    return tuple(
        _adapt_product(product, index)
        for index, product in enumerate(products)
    )


def _fetch_posts():
    # Requests runs on the server; no API calls occur when importing Django URLs.
    response = requests.get(DUMMYJSON_PRODUCTS_URL, timeout=(2, 3), allow_redirects=False)
    try:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected DummyJSON response status")
        payload = response.json()
    finally:
        response.close()
    products = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(products, list) or len(products) != 30:
        raise ValueError("Expected 30 DummyJSON products")
    ids = set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Invalid DummyJSON product")
        pk = product.get("id")
        if type(pk) is not int or pk < 1 or pk in ids:
            raise ValueError("Invalid or duplicate DummyJSON product ID")
        ids.add(pk)
        for field, limit in (("title", 300), ("description", 10000), ("category", 100)):
            value = product.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Invalid DummyJSON {field}")
        if product.get("brand") is not None and not isinstance(product["brand"], str):
            raise ValueError("Invalid DummyJSON brand")
        if product.get("meta") is not None and not isinstance(product["meta"], dict):
            raise ValueError("Invalid DummyJSON metadata")
        try:
            price = Decimal(str(product["price"]))
            if not price.is_finite() or not 0 <= price <= Decimal("1000000000"):
                raise ValueError("Invalid DummyJSON price")
        except (KeyError, ArithmeticError) as error:
            raise ValueError("Invalid DummyJSON price") from error
    return tuple(_adapt_product(product, index) for index, product in enumerate(products))


def _cache_get(cache, key):
    try:
        return cache.get(key)
    except (OSError, ValueError):
        logger.warning("Wanted sample cache unavailable while reading")
        return None


def _cache_set(cache, key, posts, seconds):
    try:
        cache.set(key, posts, timeout=seconds)
    except (OSError, ValueError):
        logger.warning("Wanted sample cache unavailable while writing")


def refresh_sample_wanted_posts():
    """API → ten-minute server cache; on failure, last-good data → snapshot."""
    cache = caches["wanted_samples"]
    cached = _cache_get(cache, CACHE_KEY)
    if cached is not None:
        return cached
    try:
        posts = _fetch_posts()
    except (requests.RequestException, ValueError, ArithmeticError, TypeError):
        logger.warning("DummyJSON unavailable or invalid; using Wanted sample fallback")
        posts = _cache_get(cache, STALE_KEY) or _snapshot_posts()
        # Briefly cache the fallback so an outage does not trigger a call on
        # every search keystroke. Retry the API after one minute.
        _cache_set(cache, CACHE_KEY, posts, FALLBACK_SECONDS)
        return posts
    _cache_set(cache, STALE_KEY, posts, STALE_SECONDS)
    _cache_set(cache, CACHE_KEY, posts, CACHE_SECONDS)
    return posts


def get_sample_wanted_posts():
    """Pages display persisted WantedPost rows; importing is an explicit operation."""
    return ()


# Offline fixture and API adapter, never fetched by page rendering.
SAMPLE_WANTED_POSTS = _snapshot_posts()
