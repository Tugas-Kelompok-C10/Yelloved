from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from items.models import Item
from wanted_board.models import WantedPost


class ItemRequest(models.Model):
    """A user's request for somebody else's item (optionally offering a swap item)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Menunggu'
        ACCEPTED = 'accepted', 'Diterima'
        REJECTED = 'rejected', 'Ditolak'
        CANCELLED = 'cancelled', 'Dibatalkan'

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='requests')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='item_requests')
    offered_item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='swap_offers', verbose_name='Barang yang ditukarkan')
    # Nominal yang ditawarkan peminta (Rupiah). Hanya dipakai untuk listing bertipe Jual,
    # jadi boleh kosong (request lama, barang gratis, barang tukar).
    offer_price = models.DecimalField('Nominal penawaran', max_digits=14, decimal_places=2,
                                      null=True, blank=True, validators=[MinValueValidator(1)])
    message = models.TextField('Pesan', max_length=1000, blank=True)
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
            raise ValidationError('Barang katalog inspirasi tidak dapat direquest.')
        if item.owner_id == self.requester_id:
            raise ValidationError('Kamu tidak bisa merequest barangmu sendiri.')
        if item.status != Item.Status.AVAILABLE:
            raise ValidationError('Barang ini sudah tidak tersedia.')
        if self._state.adding and ItemRequest.objects.filter(
                item=item, requester_id=self.requester_id, status=self.Status.PENDING).exists():
            raise ValidationError('Kamu sudah mengajukan request untuk barang ini.')
        if item.listing_type == Item.ListingType.SWAP:
            if self.offered_item_id is None:
                errors['offered_item'] = 'Pilih barang yang ingin kamu tukarkan.'
            elif self.offered_item.owner_id != self.requester_id or \
                    self.offered_item.status != Item.Status.AVAILABLE or self.offered_item.source != 'user':
                errors['offered_item'] = 'Barang tukar harus milikmu dan masih tersedia.'
        elif self.offered_item_id is not None:
            errors['offered_item'] = 'Barang tukar hanya untuk listing bertipe Tukar.'
        if self.offer_price is not None and item.listing_type != Item.ListingType.SALE:
            errors['offer_price'] = 'Nominal penawaran hanya untuk listing bertipe Jual.'
        if errors:
            raise ValidationError(errors)

    @property
    def owner(self):
        return self.item.owner

    @property
    def offer_price_display(self):
        """Contoh: Rp45.000. Kosong jika peminta tidak menawar."""
        if self.offer_price is None:
            return ''
        return 'Rp' + f'{self.offer_price:,.0f}'.replace(',', '.')

    def __str__(self):
        return f'Request {self.requester} untuk {self.item}'


class ItemOffer(models.Model):
    """An item offered by its owner in response to somebody's wanted post."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Menunggu'
        ACCEPTED = 'accepted', 'Diterima'
        REJECTED = 'rejected', 'Ditolak'
        WITHDRAWN = 'withdrawn', 'Ditarik'

    wanted_post = models.ForeignKey(WantedPost, on_delete=models.CASCADE, related_name='item_offers')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='wanted_offers')
    offerer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='item_offers')
    message = models.TextField('Pesan', max_length=1000, blank=True)
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
        if self.wanted_post_id is None or self.item_id is None or self.offerer_id is None:
            return
        if self.wanted_post.requester_id == self.offerer_id:
            raise ValidationError('Kamu tidak bisa menawarkan barang ke wanted post milikmu sendiri.')
        if self.wanted_post.status != WantedPost.Status.OPEN:
            raise ValidationError('Wanted post ini tidak lagi menerima penawaran.')
        if self.item.owner_id != self.offerer_id or self.item.source != 'user':
            raise ValidationError({'item': 'Kamu hanya bisa menawarkan barang milikmu sendiri.'})
        if self.item.status != Item.Status.AVAILABLE:
            raise ValidationError({'item': 'Barang ini sudah tidak tersedia.'})
        if self._state.adding and ItemOffer.objects.filter(
                wanted_post=self.wanted_post, item=self.item).exists():
            raise ValidationError({'item': 'Barang ini sudah kamu tawarkan untuk wanted post tersebut.'})

    def __str__(self):
        return f'{self.item} untuk {self.wanted_post}'
