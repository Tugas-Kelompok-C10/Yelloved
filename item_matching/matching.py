"""Match available items with wanted posts."""
import re
from dataclasses import dataclass, field
from decimal import Decimal

from items.models import Item
from wanted_board.models import WantedPost

CATEGORY_MAP = {
    Item.Category.FASHION: WantedPost.Category.FASHION,
    Item.Category.ELECTRONICS: WantedPost.Category.ELECTRONICS,
    Item.Category.BOOKS: WantedPost.Category.BOOKS,
    Item.Category.HOME: WantedPost.Category.HOME,
    Item.Category.SKINCARE: WantedPost.Category.SKINCARE,
    Item.Category.KITCHEN_HOUSEWARE: WantedPost.Category.KITCHEN_HOUSEWARE,
    Item.Category.ACCESSORIES: WantedPost.Category.OTHER,
}
STOPWORDS = {'yang', 'dan', 'untuk', 'dengan', 'atau', 'cari', 'butuh', 'mencari', 'the', 'for',
             'and', 'with', 'looking', 'need', 'bekas', 'second', 'preloved', 'barang'}
MIN_SCORE = 3
CANDIDATE_LIMIT = 300


@dataclass
class Match:
    item: Item
    wanted_post: WantedPost
    score: int
    reasons: list = field(default_factory=list)


def _tokens(text):
    return {t for t in re.findall(r'[a-z0-9]+', (text or '').casefold()) if len(t) >= 3 and t not in STOPWORDS}


def price_in_idr(item):
    """Item price in rupiah (legacy USD rows are converted), or None when unpriced."""
    if item.price is None:
        return None
    if item.currency == 'USD':
        from items.import_catalog import rupiah_from_usd
        return rupiah_from_usd(item.price)
    return Decimal(item.price)


def evaluate(item, wanted_post):
    """Return a Match when `item` plausibly fulfils `wanted_post`, otherwise None."""
    if item.owner_id is None or item.source != 'user' or item.owner_id == wanted_post.requester_id:
        return None
    if item.status != Item.Status.AVAILABLE or wanted_post.status != WantedPost.Status.OPEN:
        return None

    # A wanted post only describes the requested item and maximum budget.
    if item.listing_type == Item.ListingType.SWAP:
        return None
    price = price_in_idr(item)
    if wanted_post.budget is not None and price is not None and price > wanted_post.budget:
        return None

    score, reasons = 0, []
    if CATEGORY_MAP.get(item.category) == wanted_post.category:
        score += 3
        reasons.append('Same category')
    shared_title = _tokens(item.title) & _tokens(wanted_post.title)
    if shared_title:
        score += 2 * min(len(shared_title), 3)
        reasons.append('Matching keywords: ' + ', '.join(sorted(shared_title)))
    shared_desc = (_tokens(item.title + ' ' + item.description)
                   & _tokens(wanted_post.description)) - shared_title
    if shared_desc:
        score += min(len(shared_desc), 2)
        reasons.append('Similar description')
    if not shared_title and not shared_desc and score == 0:
        return None
    if wanted_post.budget is not None and price is not None:
        score += 1
        reasons.append('Within budget')
    elif item.listing_type == Item.ListingType.FREE:
        score += 1
        reasons.append('Free')
    if _tokens(item.location) & _tokens(wanted_post.location):
        score += 1
        reasons.append('Nearby location')
    if score < MIN_SCORE:
        return None
    return Match(item=item, wanted_post=wanted_post, score=score, reasons=reasons)


def suggest_items_for_wanted(wanted_post, limit=10):
    candidates = (Item.objects.filter(status=Item.Status.AVAILABLE, source='user', owner__isnull=False)
                  .exclude(owner_id=wanted_post.requester_id).select_related('owner')[:CANDIDATE_LIMIT])
    matches = [m for m in (evaluate(i, wanted_post) for i in candidates) if m]
    return sorted(matches, key=lambda m: (-m.score, -m.item.pk))[:limit]


def suggest_wanted_for_item(item, limit=10):
    candidates = (WantedPost.objects.filter(status=WantedPost.Status.OPEN)
                  .exclude(requester_id=item.owner_id).select_related('requester')[:CANDIDATE_LIMIT])
    matches = [m for m in (evaluate(item, p) for p in candidates) if m]
    return sorted(matches, key=lambda m: (-m.score, -m.wanted_post.created_at.timestamp(), m.wanted_post.pk.int))[:limit]
