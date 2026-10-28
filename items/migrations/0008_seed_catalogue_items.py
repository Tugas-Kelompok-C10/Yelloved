"""Offline, frozen student catalogue inspired by DummyJSON Products.

IDs 10000001..10000020 are local seed identifiers, not DummyJSON product IDs.
Keep source='user' for the existing Item Matching contract; dedicated demo owner
plus reserved external_id identify catalogue items using existing Item.is_catalog.
Do not import live models, the mutable photo mapping, or fetch the network here.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations

DEMO_USERNAME = 'yelloved_community'
SOURCE_REFERENCE = 'https://dummyjson.com/products'
# Frozen copies of the curated profiles and photos in items/catalog_photos.json.
# (local ID, title, category, condition, preloved IDR price, location, local image)
SEED_ITEMS = ((10000001,
  'Kaos Katun Merah Muda',
  'fashion',
  'like_new',
  20000,
  'Area UI, Depok',
  '/static/img/items/catalog/item-001.webp'),
 (10000002,
  'Kemeja Flanel Biru',
  'fashion',
  'good',
  45000,
  'Pondok Cina, Depok',
  '/static/img/items/catalog/item-002.webp'),
 (10000003,
  'Hoodie Santai Bekas',
  'fashion',
  'fair',
  75000,
  'Kukusan, Depok',
  '/static/img/items/catalog/item-003.webp'),
 (10000004,
  'Tote Bag Kanvas untuk Buku',
  'fashion',
  'like_new',
  25000,
  'Beji, Depok',
  '/static/img/items/catalog/item-006.webp'),
 (10000005,
  'Ransel Hitam untuk Kuliah',
  'fashion',
  'good',
  65000,
  'Margonda, Depok',
  '/static/img/items/catalog/item-007.webp'),
 (10000006,
  'Sepatu Kanvas Putih',
  'fashion',
  'fair',
  80000,
  'Area UI, Depok',
  '/static/img/items/catalog/item-008.webp'),
 (10000007,
  'Set Buku Pemrograman',
  'books',
  'like_new',
  45000,
  'Pondok Cina, Depok',
  '/static/img/items/catalog/item-015.webp'),
 (10000008,
  'Buku Kalkulus Dasar',
  'books',
  'good',
  50000,
  'Kukusan, Depok',
  '/static/img/items/catalog/item-016.webp'),
 (10000009,
  'Novel Bekas Bacaan Santai',
  'books',
  'fair',
  25000,
  'Beji, Depok',
  '/static/img/items/catalog/item-017.webp'),
 (10000010,
  'Kalkulator Scientific Casio',
  'books',
  'like_new',
  85000,
  'Margonda, Depok',
  '/static/img/items/catalog/item-018.webp'),
 (10000011,
  'Binder Kuliah Berwarna',
  'books',
  'good',
  None,
  'Area UI, Depok',
  '/static/img/items/catalog/item-019.webp'),
 (10000012,
  'Keyboard Kabel Hitam',
  'electronics',
  'fair',
  75000,
  'Pondok Cina, Depok',
  '/static/img/items/catalog/item-026.webp'),
 (10000013,
  'Mouse Nirkabel Abu-abu',
  'electronics',
  'like_new',
  45000,
  'Kukusan, Depok',
  '/static/img/items/catalog/item-027.webp'),
 (10000014,
  'Lampu Belajar Meja',
  'electronics',
  'good',
  60000,
  'Beji, Depok',
  '/static/img/items/catalog/item-029.webp'),
 (10000015,
  'Kipas Meja Kecil',
  'electronics',
  'fair',
  85000,
  'Margonda, Depok',
  '/static/img/items/catalog/item-030.webp'),
 (10000016,
  'Meja Lipat Kayu',
  'home',
  'like_new',
  100000,
  'Area UI, Depok',
  '/static/img/items/catalog/item-039.webp'),
 (10000017,
  'Hanger Pakaian Kawat',
  'home',
  'good',
  None,
  'Pondok Cina, Depok',
  '/static/img/items/catalog/item-043.webp'),
 (10000018,
  'Tempat Pensil Kayu',
  'home',
  'fair',
  25000,
  'Kukusan, Depok',
  '/static/img/items/catalog/item-044.webp'),
 (10000019,
  'Rak Sepatu Kayu',
  'home',
  'like_new',
  45000,
  'Beji, Depok',
  '/static/img/items/catalog/item-049.webp'),
 (10000020,
  'Kotak Penyimpanan Plastik',
  'home',
  'good',
  25000,
  'Margonda, Depok',
  '/static/img/items/catalog/item-050.webp'))


def seed_catalogue(apps, schema_editor):
    Item = apps.get_model('items', 'Item')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    alias = schema_editor.connection.alias
    seller, _ = User.objects.using(alias).get_or_create(
        username=DEMO_USERNAME,
        defaults={'first_name': 'Yelloved', 'last_name': 'Community',
                  'password': make_password(None), 'is_staff': False, 'is_superuser': False},
    )
    # Never take over a real account or silently reassign another user's listing.
    if (not seller.password.startswith('!') or seller.is_staff or seller.is_superuser
            or seller.first_name != 'Yelloved' or seller.last_name != 'Community'):
        raise RuntimeError('Catalogue demo username belongs to another account; no account may be repurposed.')
    for external_id, title, category, condition, price, location, image_url in SEED_ITEMS:
        item, created = Item.objects.using(alias).get_or_create(
            external_id=external_id,
            defaults={
                'owner_id': seller.pk, 'title': title,
                'description': (f'{title} preloved untuk kegiatan kuliah dan kebutuhan kos. '
                                'Memiliki bekas pemakaian wajar dan dapat diambil di sekitar UI/Depok. '
                                'Listing demo komunitas untuk mencoba fitur Yelloved.'),
                'category': category, 'condition': condition,
                'price': None if price is None else Decimal(price), 'currency': 'IDR',
                'listing_type': 'free' if price is None else 'sale',
                'location': location, 'image_url': image_url, 'status': 'available', 'source': 'user',
            },
        )
        if not created and (item.owner_id != seller.pk or item.source != 'user'
                            or item.title != title or item.image_url != image_url):
            raise RuntimeError(f'Catalogue seed ID {external_id} belongs to different data; existing item is unchanged.')


def unseed_catalogue(apps, schema_editor):
    Item = apps.get_model('items', 'Item')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    alias = schema_editor.connection.alias
    seller = User.objects.using(alias).filter(
        username=DEMO_USERNAME, first_name='Yelloved', last_name='Community',
        password__startswith='!', is_staff=False, is_superuser=False,
    ).first()
    if seller is None:
        return
    for external_id, title, _, _, _, _, image_url in SEED_ITEMS:
        # Conservative reverse: preserve anything reassigned or repurposed by users.
        Item.objects.using(alias).filter(
            external_id=external_id, owner_id=seller.pk, source='user',
            title=title, image_url=image_url,
        ).delete()
    # The seller may be referenced by other catalogue items/requests. Keep it.


class Migration(migrations.Migration):
    dependencies = [
        ('items', '0007_item_liked_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.RunPython(seed_catalogue, unseed_catalogue)]
