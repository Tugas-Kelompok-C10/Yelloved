from decimal import Decimal, InvalidOperation

import requests
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from items.demo_seller import get_demo_seller

from items.import_catalog import localize_product, catalog_photos
from items.models import Item


class Command(BaseCommand):
    help = 'Impor katalog mahasiswa sebagai listing penjual demo; refresh tidak menyentuh pemilik asli.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--refresh', action='store_true')

    def handle(self, *args, **options):
        limit = options['limit']
        if not 50 <= limit <= len(catalog_photos()):
            raise CommandError('--limit harus antara 50 dan 100 (jumlah foto katalog lokal).')
        try:
            # Ambil katalog lengkap agar 50 hasil pertama bukan kosmetik/sembako saja.
            response = requests.get('https://dummyjson.com/products', params={'limit': 0}, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise CommandError(f'Gagal mengambil DummyJSON: {exc}') from exc
        products = payload.get('products') if isinstance(payload, dict) else None
        if not isinstance(products, list):
            raise CommandError('Daftar produk API tidak valid. Database tidak diubah.')
        prepared = []
        seen = set()
        try:
            for product in sorted(products, key=lambda entry: entry['id']):
                external_id = product['id']
                if type(external_id) is not int or external_id <= 0 or external_id in seen:
                    raise ValueError('ID produk tidak valid/duplikat.')
                seen.add(external_id)
                localized = localize_product(product, len(prepared))
                if localized is None:
                    continue
                price = Decimal(str(product['price']))
                if not price.is_finite() or price < 0:
                    raise ValueError('Harga sumber tidak valid.')
                defaults = {**localized, 'currency': 'IDR',
                            'status': Item.Status.AVAILABLE, 'source': 'dummyjson', 'owner': None}
                Item(external_id=external_id, **defaults).full_clean(validate_unique=False)
                prepared.append((external_id, defaults))
        except (KeyError, TypeError, ValueError, InvalidOperation, ValidationError) as exc:
            raise CommandError(f'Data API tidak valid; database tidak diubah: {exc}') from exc
        prepared = prepared[:limit]
        if len(prepared) < 50:
            raise CommandError('Kurang dari 50 produk relevan. Database tidak diubah.')
        identifiers = [external_id for external_id, _ in prepared]
        created = 0
        deleted = 0
        with transaction.atomic():
            seller = get_demo_seller()
            imported = Q(source='dummyjson', owner__isnull=True) | Q(
                owner=seller, external_id__isnull=False, source__in=['user', 'dummyjson'])
            conflicts = Item.objects.filter(external_id__in=identifiers).exclude(imported)
            if conflicts.exists():
                raise CommandError('ID API bertabrakan dengan item milik pengguna. Database tidak diubah.')
            for external_id, defaults in prepared:
                # Matching accepts only user listings. external_id retains API provenance.
                defaults.update(owner=seller, source='user')
                _, new = Item.objects.update_or_create(external_id=external_id, defaults=defaults)
                created += int(new)
            if options['refresh']:
                deleted, _ = Item.objects.filter(imported).exclude(external_id__in=identifiers).delete()
        count = Item.objects.filter(owner=seller, external_id__isnull=False, status=Item.Status.AVAILABLE).count()
        self.stdout.write(self.style.SUCCESS(f'Impor selesai: {created} baru, {len(prepared) - created} diperbarui, {deleted} item API lama dihapus. {count} item API tersedia.'))
        self.stdout.write('Harga seed preloved terkurasi dalam Rupiah; tersedia barang Gratis. Item manual tidak diubah.')
        self.stdout.write('Refresh: env/bin/python3 manage.py import_dummyjson_items --limit 100 --refresh')
