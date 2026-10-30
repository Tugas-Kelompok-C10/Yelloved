"""State transitions for requests and offers. Views stay thin; rules live here."""
from django.db import transaction
from django.utils import timezone

from items.models import Item
from wanted_board.models import WantedPost

from .models import ItemOffer, ItemRequest


class MatchingError(Exception):
    """A transition was refused; the message is safe to show to the user."""


def release_item(item):
    """Drop pending proposals that depend on `item` once it is no longer available."""
    ItemRequest.objects.filter(item=item, status=ItemRequest.Status.PENDING).update(
        status=ItemRequest.Status.REJECTED, updated_at=timezone.now())
    ItemRequest.objects.filter(offered_item=item, status=ItemRequest.Status.PENDING).update(
        status=ItemRequest.Status.CANCELLED, updated_at=timezone.now())
    ItemOffer.objects.filter(item=item, status=ItemOffer.Status.PENDING).update(
        status=ItemOffer.Status.WITHDRAWN, updated_at=timezone.now())


def close_offers_for(wanted_post):
    """A wanted post that is no longer open cannot keep pending item offers."""
    ItemOffer.objects.filter(wanted_post=wanted_post, status=ItemOffer.Status.PENDING).update(
        status=ItemOffer.Status.REJECTED, updated_at=timezone.now())


def _reserve(*items):
    """Take items off the market and drop pending proposals that depended on them."""
    for item in items:
        if item is None:
            continue
        Item.objects.filter(pk=item.pk).update(status=Item.Status.UNAVAILABLE)
        release_item(item)


def _lock(model, pk):
    return model.objects.select_for_update().get(pk=pk)


@transaction.atomic
def accept_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    item = _lock(Item, req.item_id)
    if item.owner_id != user.pk:
        raise MatchingError('Only the item owner can accept this request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('This request has already been processed.')
    if item.status != Item.Status.AVAILABLE:
        raise MatchingError('This item is no longer available.')
    swap_item = req.offered_item
    if item.listing_type == Item.ListingType.SWAP and swap_item is None:
        raise MatchingError('The requester\'s swap item no longer exists.')
    if swap_item is not None and swap_item.status != Item.Status.AVAILABLE:
        raise MatchingError('The requester\'s swap item is no longer available.')
    req.status = ItemRequest.Status.ACCEPTED
    req.save(update_fields=['status', 'updated_at'])
    _reserve(item, swap_item)
    return req


@transaction.atomic
def reject_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    if req.item.owner_id != user.pk:
        raise MatchingError('Only the item owner can reject this request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('This request has already been processed.')
    req.status = ItemRequest.Status.REJECTED
    req.save(update_fields=['status', 'updated_at'])
    return req


@transaction.atomic
def cancel_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    if req.requester_id != user.pk:
        raise MatchingError('Only the requester can cancel this request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('Only pending requests can be cancelled.')
    req.status = ItemRequest.Status.CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    return req


@transaction.atomic
def accept_offer(offer_id, user):
    offer = _lock(ItemOffer, offer_id)
    post = _lock(WantedPost, offer.wanted_post_id)
    item = _lock(Item, offer.item_id) if offer.item_id else None
    if post.requester_id != user.pk:
        raise MatchingError('Only the wanted post owner can accept this offer.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('This offer has already been processed.')
    if post.status != WantedPost.Status.OPEN:
        raise MatchingError('This wanted post is no longer open.')
    if item and item.status != Item.Status.AVAILABLE:
        raise MatchingError('The offered item is no longer available.')
    offer.status = ItemOffer.Status.ACCEPTED
    offer.save(update_fields=['status', 'updated_at'])
    ItemOffer.objects.filter(wanted_post=post, status=ItemOffer.Status.PENDING).exclude(
        pk=offer.pk).update(status=ItemOffer.Status.REJECTED)
    post.status = WantedPost.Status.FULFILLED
    post.save(update_fields=['status', 'updated_at'])
    _reserve(item)
    return offer


@transaction.atomic
def reject_offer(offer_id, user):
    offer = _lock(ItemOffer, offer_id)
    if offer.wanted_post.requester_id != user.pk:
        raise MatchingError('Only the wanted post owner can reject this offer.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('This offer has already been processed.')
    offer.status = ItemOffer.Status.REJECTED
    offer.save(update_fields=['status', 'updated_at'])
    return offer


@transaction.atomic
def withdraw_offer(offer_id, user):
    offer = _lock(ItemOffer, offer_id)
    if offer.offerer_id != user.pk:
        raise MatchingError('Only the person who made the offer can withdraw it.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('Only pending offers can be withdrawn.')
    offer.status = ItemOffer.Status.WITHDRAWN
    offer.save(update_fields=['status', 'updated_at'])
    return offer
