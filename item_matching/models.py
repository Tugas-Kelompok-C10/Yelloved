from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from wanted_board.validators import validate_reference_image

from items.models import Item
from wanted_board.models import WantedPost


class ItemRequest(models.Model):
    """A user's request for somebody else's item (optionally offering a swap item)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='requests')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='item_requests')
    offered_item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='swap_offers', verbose_name='Item to swap')
    # Amount the requester offers (Rupiah). Only used for Sale listings,
    # so it may be empty (old requests, free items, swap items).
    offer_price = models.DecimalField('Offer amount', max_digits=14, decimal_places=2,
                                      null=True, blank=True, validators=[MinValueValidator(1)])
    message = models.TextField('Message', max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['item', 'requester'], condition=Q(status='pending'),
                                    name='unique_pending_request_per_item_and_user'),
        ]

    def clean(self):
        super().clean()
        if self.item_id is None or self.requester_id is None:
            return
        item, errors = self.item, {}
        if item.owner_id is None or item.source != 'user':
            raise ValidationError('Inspiration catalog items cannot be requested.')
        if item.owner_id == self.requester_id:
            raise ValidationError('You cannot request your own item.')
        if item.status != Item.Status.AVAILABLE:
            raise ValidationError('This item is no longer available.')
        if self._state.adding and ItemRequest.objects.filter(
                item=item, requester_id=self.requester_id, status=self.Status.PENDING).exists():
            raise ValidationError('You already have a pending request for this item.')
        if item.listing_type == Item.ListingType.SWAP:
            if self.offered_item_id is None:
                errors['offered_item'] = 'Choose the item you want to swap.'
            elif self.offered_item.owner_id != self.requester_id or \
                    self.offered_item.status != Item.Status.AVAILABLE or self.offered_item.source != 'user':
                errors['offered_item'] = 'The swap item must be yours and still available.'
        elif self.offered_item_id is not None:
            errors['offered_item'] = 'A swap item is only for Swap listings.'
        if self.offer_price is not None and item.listing_type != Item.ListingType.SALE:
            errors['offer_price'] = 'An offer amount is only for Sale listings.'
        if errors:
            raise ValidationError(errors)

    @property
    def owner(self):
        return self.item.owner

    @property
    def offer_price_display(self):
        """Example: Rp45.000. Empty when the requester did not make an offer."""
        if self.offer_price is None:
            return ''
        return 'Rp' + f'{self.offer_price:,.0f}'.replace(',', '.')

    def __str__(self):
        return f'Request by {self.requester} for {self.item}'


class PhotoOfferQuota(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class PhotoOfferSendEvent(models.Model):
    # Keep send history even when a wanted post (and its offers) is deleted.
    quota = models.ForeignKey(PhotoOfferQuota, on_delete=models.CASCADE, related_name='events')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['quota', 'created_at'], name='photo_offer_send_window')]


class ItemOffer(models.Model):
    """An item offered by its owner in response to somebody's wanted post."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    wanted_post = models.ForeignKey(WantedPost, on_delete=models.CASCADE, related_name='item_offers')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='wanted_offers', null=True, blank=True)
    photo = models.ImageField(upload_to='item_offers/', blank=True, validators=[
        FileExtensionValidator(allowed_extensions=('jpg', 'jpeg', 'png', 'webp')), validate_reference_image])
    offered_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        validators=[MinValueValidator(0)])
    submission_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    offerer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='item_offers')
    message = models.TextField('Message', max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['wanted_post', 'item'], name='unique_item_offer_per_wanted_post'),
        ]

    def clean(self):
        super().clean()
        if self.wanted_post_id is None or self.offerer_id is None:
            return
        if self.wanted_post.requester_id == self.offerer_id:
            raise ValidationError('You cannot offer an item on your own wanted post.')
        if self.wanted_post.status != WantedPost.Status.OPEN:
            raise ValidationError('This wanted post is no longer accepting offers.')
        if self.item_id is None:
            if not self.photo or self.offered_price is None or not self.message.strip():
                raise ValidationError('Include an item photo, price, and short description.')
            return
        if self.item.owner_id != self.offerer_id or self.item.source != 'user':
            raise ValidationError({'item': 'You can only offer your own items.'})
        if self.item.status != Item.Status.AVAILABLE:
            raise ValidationError({'item': 'This item is no longer available.'})
        if self._state.adding and ItemOffer.objects.filter(
                wanted_post=self.wanted_post, item=self.item).exists():
            raise ValidationError({'item': 'You already offered this item on this wanted post.'})

    def __str__(self):
        return f'{self.display_title} offered for {self.wanted_post}'

    @property
    def display_title(self):
        return self.item.title if self.item_id else self.wanted_post.title

    @property
    def display_image_url(self):
        return self.item.display_image_url if self.item_id else (self.photo.url if self.photo else '')

    @property
    def price_display(self):
        if self.offered_price is not None:
            return 'Rp' + f'{self.offered_price:,.0f}'.replace(',', '.')
        return self.item.price_display if self.item_id else '—'
