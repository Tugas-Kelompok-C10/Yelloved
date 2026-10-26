"""State transitions for requests and offers. Views stay thin; rules live here."""
from django.db import transaction

from items.models import Item
from wanted_board.models import WantedPost

from .models import ItemOffer, ItemRequest


class MatchingError(Exception):
    """A transition was refused; the message is safe to show to the user."""


def _reserve(*items):
    """Take items off the market and drop pending proposals that depended on them."""
    for item in items:
        if item is None:
            continue
        Item.objects.filter(pk=item.pk).update(status=Item.Status.UNAVAILABLE)
        ItemRequest.objects.filter(item=item, status=ItemRequest.Status.PENDING).update(
            status=ItemRequest.Status.REJECTED)
        ItemRequest.objects.filter(offered_item=item, status=ItemRequest.Status.PENDING).update(
            status=ItemRequest.Status.CANCELLED)
        ItemOffer.objects.filter(item=item, status=ItemOffer.Status.PENDING).update(
            status=ItemOffer.Status.WITHDRAWN)


def _lock(model, pk):
    return model.objects.select_for_update().get(pk=pk)


@transaction.atomic
def accept_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    item = _lock(Item, req.item_id)
    if item.owner_id != user.pk:
        raise MatchingError('Hanya pemilik barang yang dapat menerima request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('Request ini sudah diproses.')
    if item.status != Item.Status.AVAILABLE:
        raise MatchingError('Barang ini sudah tidak tersedia.')
    swap_item = req.offered_item
    if swap_item is not None and swap_item.status != Item.Status.AVAILABLE:
        raise MatchingError('Barang tukar dari peminta sudah tidak tersedia.')
    req.status = ItemRequest.Status.ACCEPTED
    req.save(update_fields=['status', 'updated_at'])
    _reserve(item, swap_item)
    return req


@transaction.atomic
def reject_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    if req.item.owner_id != user.pk:
        raise MatchingError('Hanya pemilik barang yang dapat menolak request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('Request ini sudah diproses.')
    req.status = ItemRequest.Status.REJECTED
    req.save(update_fields=['status', 'updated_at'])
    return req


@transaction.atomic
def cancel_request(request_id, user):
    req = _lock(ItemRequest, request_id)
    if req.requester_id != user.pk:
        raise MatchingError('Hanya peminta yang dapat membatalkan request.')
    if req.status != ItemRequest.Status.PENDING:
        raise MatchingError('Hanya request yang masih menunggu yang dapat dibatalkan.')
    req.status = ItemRequest.Status.CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    return req


@transaction.atomic
def accept_offer(offer_id, user):
    offer = _lock(ItemOffer, offer_id)
    post = _lock(WantedPost, offer.wanted_post_id)
    item = _lock(Item, offer.item_id)
    if post.requester_id != user.pk:
        raise MatchingError('Hanya pembuat wanted post yang dapat menerima penawaran.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('Penawaran ini sudah diproses.')
    if post.status != WantedPost.Status.OPEN:
        raise MatchingError('Wanted post ini sudah tidak terbuka.')
    if item.status != Item.Status.AVAILABLE:
        raise MatchingError('Barang yang ditawarkan sudah tidak tersedia.')
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
        raise MatchingError('Hanya pembuat wanted post yang dapat menolak penawaran.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('Penawaran ini sudah diproses.')
    offer.status = ItemOffer.Status.REJECTED
    offer.save(update_fields=['status', 'updated_at'])
    return offer


@transaction.atomic
def withdraw_offer(offer_id, user):
    offer = _lock(ItemOffer, offer_id)
    if offer.offerer_id != user.pk:
        raise MatchingError('Hanya pemilik penawaran yang dapat menariknya.')
    if offer.status != ItemOffer.Status.PENDING:
        raise MatchingError('Hanya penawaran yang masih menunggu yang dapat ditarik.')
    offer.status = ItemOffer.Status.WITHDRAWN
    offer.save(update_fields=['status', 'updated_at'])
    return offer
