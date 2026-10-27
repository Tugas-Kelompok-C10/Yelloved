from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from .validators import validate_item_image


class Item(models.Model):
    class Category(models.TextChoices):
        FASHION = 'fashion', 'Fashion'
        ELECTRONICS = 'electronics', 'Elektronik'
        BOOKS = 'books', 'Buku & Keperluan Kuliah'
        HOME = 'home', 'Perlengkapan Kos'
        SKINCARE = 'skincare', 'Skincare'
        KITCHEN_HOUSEWARE = 'kitchen_houseware', 'Alat Masak & Houseware'
        ACCESSORIES = 'accessories', 'Aksesoris'

    class Condition(models.TextChoices):
        LIKE_NEW = 'like_new', 'Sangat Baik'
        GOOD = 'good', 'Baik'
        FAIR = 'fair', 'Layak Pakai'

    class ListingType(models.TextChoices):
        SALE = 'sale', 'Jual'
        FREE = 'free', 'Gratis'
        SWAP = 'swap', 'Tukar'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Tersedia'
        SOLD = 'sold', 'Terjual'
        UNAVAILABLE = 'unavailable', 'Tidak Tersedia'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='items')
    title = models.CharField('Nama barang', max_length=200)
    description = models.TextField('Deskripsi', max_length=5000)
    category = models.CharField('Kategori', max_length=20, choices=Category.choices)
    condition = models.CharField('Kondisi', max_length=20, choices=Condition.choices)
    price = models.DecimalField('Harga', max_digits=14, decimal_places=2, null=True,
                                blank=True, validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField(max_length=3, choices=[('IDR', 'IDR'), ('USD', 'USD')], default='IDR')
    listing_type = models.CharField('Tipe listing', max_length=10, choices=ListingType.choices, default=ListingType.SALE)
    location = models.CharField('Lokasi', max_length=200)
    image_url = models.CharField('URL foto', max_length=1000, blank=True, validators=[validate_item_image])
    status = models.CharField('Status', max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True, editable=False)
    source = models.CharField(max_length=20, choices=[('user', 'Pengguna'), ('dummyjson', 'DummyJSON')], default='user', editable=False)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0) | models.Q(price__isnull=True), name='items_price_nonnegative')]

    def clean(self):
        super().clean()
        if self.listing_type == self.ListingType.SALE and self.price is None:
            raise ValidationError({'price': 'Harga wajib diisi untuk barang yang dijual.'})
        if self.listing_type in (self.ListingType.FREE, self.ListingType.SWAP):
            self.price = None

    def get_absolute_url(self):
        return reverse('items:item_detail', args=[self.pk])

    @property
    def price_display(self):
        if self.listing_type == self.ListingType.FREE:
            return 'Gratis'
        if self.listing_type == self.ListingType.SWAP:
            return 'Tukar'
        if self.price is None:
            return 'Harga belum tersedia'
        from .import_catalog import rupiah_from_usd
        price = rupiah_from_usd(self.price) if self.currency == 'USD' else self.price
        return 'Rp' + f'{price:,.0f}'.replace(',', '.')

    @property
    def display_image_url(self):
        from django.templatetags.static import static
        if self.source != 'dummyjson' and self.image_url:
            return self.image_url
        if self.image_url.startswith('/static/img/items/catalog/'):
            return static(self.image_url.removeprefix('/static/'))
        return self.fallback_image_url

    @property
    def fallback_image_url(self):
        from django.templatetags.static import static
        category = {
            self.Category.SKINCARE: 'fashion',
            self.Category.KITCHEN_HOUSEWARE: 'home',
        }.get(self.category, self.category)
        if category not in {'fashion', 'electronics', 'books', 'home', 'accessories'}:
            category = 'home'
        return static(f'img/items/placeholder-{category}.svg')

    def __str__(self):
        return self.title
