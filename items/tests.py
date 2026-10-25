from io import StringIO
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from .forms import ItemForm
from .models import Item


class ItemsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='seller_private', email='private@example.com', password='test-password')
        self.other = get_user_model().objects.create_user(username='other', password='test-password')
        self.data = {'title': 'Kemeja', 'description': 'Linen kampus', 'category': 'fashion', 'condition': 'good', 'price': '45000', 'listing_type': 'sale', 'location': 'Depok', 'image_url': 'https://example.com/photo.jpg', 'status': 'available'}
        self.item = Item.objects.create(owner=self.owner, **self.data)

    def test_guest_redirect_and_seller_privacy(self):
        response = self.client.get(reverse('items:item_create'))
        self.assertRedirects(response, '/accounts/login/?next=/explore/create/', fetch_redirect_response=False)
        response = self.client.get(self.item.get_absolute_url())
        self.assertNotContains(response, self.owner.username)
        self.assertNotContains(response, self.owner.email)
        self.assertNotContains(response, 'Edit Item / Status')
        self.client.force_login(self.other)
        self.assertContains(self.client.get(self.item.get_absolute_url()), self.owner.username)

    def test_crud_and_forced_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('items:item_create'), {**self.data, 'owner': self.other.pk, 'source': 'dummyjson'})
        item = Item.objects.exclude(pk=self.item.pk).get()
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.owner, self.owner)
        self.assertEqual(item.source, 'user')
        response = self.client.post(reverse('items:item_update', args=[item.pk]), {**self.data, 'status': 'sold'})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, 'sold')
        self.assertEqual(self.client.get(reverse('items:item_delete', args=[item.pk])).status_code, 200)
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())
        self.assertEqual(self.client.post(reverse('items:item_delete', args=[item.pk])).status_code, 302)
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())

    def test_non_owner_forbidden_and_api_readonly(self):
        self.client.force_login(self.other)
        api_item = Item.objects.create(**self.data, source='dummyjson', external_id=7)
        for item in (self.item, api_item):
            for name in ('item_update', 'item_delete'):
                url = reverse('items:' + name, args=[item.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, self.data).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'available')

    def test_server_validation(self):
        for changes in ({'price': '-1'}, {'price': ''}, {'image_url': 'javascript:alert(1)'}, {'category': 'invalid'}, {'title': '   '}):
            self.assertFalse(ItemForm({**self.data, **changes}).is_valid())
        form = ItemForm({**self.data, 'listing_type': 'free', 'price': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save(commit=False).price)

    def test_filters_and_safe_json(self):
        url = reverse('items:items_json')
        response = self.client.get(url, {'q': 'LINEN', 'category': 'fashion', 'condition': 'good', 'listing_type': 'sale', 'status': 'available'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        self.assertNotIn('owner', response.json()['items'][0])
        self.assertNotContains(response, 'private@example.com')
        self.assertEqual(self.client.get(url, {'q': 'absent'}).json()['count'], 0)
        self.assertEqual(self.client.get(url, {'status': 'sold'}).json()['count'], 0)
        self.assertEqual(self.client.get(url, {'category': 'invalid'}).status_code, 400)
        self.assertContains(self.client.get(reverse('items:explore_items')), 'Kemeja')
        self.item.title = '<script>alert(1)</script>'
        self.item.save()
        self.assertNotIn('<script>alert(1)</script>', self.client.get(url).json()['html'])

    def test_pagination_and_404(self):
        Item.objects.bulk_create([Item(**self.data) for _ in range(13)])
        response = self.client.get(reverse('items:items_json'), {'page': 2})
        self.assertEqual(len(response.json()['items']), 2)
        self.assertEqual(self.client.get('/explore/99999/').status_code, 404)

    def test_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('items:item_delete', args=[self.item.pk])).status_code, 403)

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_import_is_idempotent(self, get):
        get.return_value.json.return_value = {'products': [{'id': n, 'title': f'Product {n}', 'description': 'Example', 'category': 'mens-shirts', 'price': 9.99, 'thumbnail': 'https://example.com/image.jpg'} for n in range(1, 51)]}
        for _ in range(2):
            call_command('import_dummyjson_items', limit=50, stdout=StringIO())
        self.assertEqual(Item.objects.filter(source='dummyjson').count(), 50)
        item = Item.objects.get(external_id=1)
        self.assertIsNone(item.owner)
        self.assertEqual(item.currency, 'IDR')
        self.assertEqual(item.price, 20000)
        self.assertEqual(item.price_display, 'Rp20.000')
        self.assertEqual(item.category, Item.Category.FASHION)
        get.return_value.json.return_value['products'][-1]['price'] = -1
        with self.assertRaises(CommandError):
            call_command('import_dummyjson_items', stdout=StringIO())
        self.assertEqual(Item.objects.filter(source='dummyjson').count(), 50)

    @patch('items.management.commands.import_dummyjson_items.requests.get', side_effect=requests.Timeout)
    def test_import_failure(self, get):
        with self.assertRaises(CommandError):
            call_command('import_dummyjson_items', stdout=StringIO())
        self.assertEqual(Item.objects.filter(source='dummyjson').count(), 0)

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_refresh_preserves_manual_and_owned_data(self, get):
        products = [{'id': n, 'title': f'Shirt {n}', 'category': 'mens-shirts', 'price': 9.99} for n in range(1, 51)]
        products.append({'id': 999, 'title': 'Wooden Bathroom Sink With Mirror', 'category': 'furniture', 'price': 999})
        get.return_value.json.return_value = {'products': products}
        obsolete = Item.objects.create(**self.data, source='dummyjson', external_id=999)
        owned = Item.objects.create(**self.data, source='dummyjson', external_id=998, owner=self.owner)
        manual = Item.objects.create(**self.data, external_id=997)
        before = list(Item.objects.filter(pk__in=[self.item.pk, manual.pk, owned.pk]).values())
        for _ in range(2):
            call_command('import_dummyjson_items', limit=100, refresh=True, stdout=StringIO())
        self.assertFalse(Item.objects.filter(pk=obsolete.pk).exists())
        self.assertEqual(list(Item.objects.filter(pk__in=[self.item.pk, manual.pk, owned.pk]).values()), before)
        self.assertEqual(Item.objects.filter(source='dummyjson', owner__isnull=True).count(), 50)
        imported = Item.objects.get(external_id=1)
        self.assertEqual(imported.title, 'Kaos Katun Merah Muda')
        self.assertTrue(imported.display_image_url.endswith('catalog/item-001.webp'))
        html = self.client.get(imported.get_absolute_url()).content.decode()
        self.assertNotIn('USD', html)
        self.assertNotIn('DummyJSON', html)
        self.assertContains(self.client.get('/explore/api/', {'q': 'Kaos Katun Merah Muda'}), 'Rp20.000')

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_refresh_insufficient_products_keeps_database(self, get):
        obsolete = Item.objects.create(**self.data, source='dummyjson', external_id=999)
        get.return_value.json.return_value = {'products': [{'id': 1, 'title': 'Wooden Bathroom Sink With Mirror', 'category': 'furniture', 'price': 10}]}
        with self.assertRaises(CommandError):
            call_command('import_dummyjson_items', refresh=True, stdout=StringIO())
        self.assertTrue(Item.objects.filter(pk=obsolete.pk).exists())

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_import_cannot_overwrite_manual_id_collision(self, get):
        self.item.external_id = 1
        self.item.save()
        get.return_value.json.return_value = {'products': [{'id': n, 'title': 'Shirt', 'category': 'mens-shirts', 'price': 10} for n in range(1, 51)]}
        with self.assertRaises(CommandError):
            call_command('import_dummyjson_items', refresh=True, stdout=StringIO())
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Kemeja')
        self.assertEqual(Item.objects.count(), 1)

    def test_rupiah_rounding_and_neutral_category_images(self):
        from decimal import Decimal
        from .import_catalog import rupiah_from_usd
        self.assertEqual(rupiah_from_usd('1.01'), Decimal('16000'))
        self.assertEqual(rupiah_from_usd('1.04'), Decimal('17000'))
        item = Item(**{**self.data, 'price': Decimal('9.99')}, currency='USD')
        self.assertEqual(item.price_display, 'Rp160.000')
        self.assertEqual(item.currency, 'USD')  # Display does not mutate manual data.
        item.source = 'dummyjson'
        item.category = 'electronics'
        item.title = 'Ponsel untuk Kuliah'
        self.assertTrue(item.display_image_url.endswith('placeholder-electronics.svg'))
        self.assertNotIn('example.com', item.display_image_url)
        item.source = 'user'
        self.assertEqual(item.display_image_url, self.data['image_url'])

    def test_sell_button_and_full_user_demo(self):
        explore = reverse('items:explore_items')
        create = reverse('items:item_create')
        response = self.client.get(explore)
        self.assertContains(response, '+ Jual Barang')
        self.assertContains(response, '/accounts/login/?next=/explore/create/')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(explore), 'href="/explore/create/"')
        self.assertEqual(self.client.get(create).status_code, 200)
        data = {**self.data, 'title': 'Hoodie Demo Mahasiswa'}
        response = self.client.post(create, data, follow=True)
        item = Item.objects.get(title=data['title'])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('items:item_update', args=[item.pk]))
        self.assertContains(response, reverse('items:item_delete', args=[item.pk]))
        self.assertContains(self.client.get(explore), data['title'])
        self.assertContains(self.client.get(reverse('items:items_json')), data['title'])
        data.update(title='Hoodie Demo Diperbarui', status='unavailable')
        self.client.post(reverse('items:item_update', args=[item.pk]), data)
        item.refresh_from_db()
        self.assertEqual(item.title, data['title'])
        self.assertEqual(item.status, 'unavailable')
        delete = reverse('items:item_delete', args=[item.pk])
        self.assertContains(self.client.get(delete), 'Ya, Hapus Item')
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())
        self.client.post(delete)
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertNotContains(self.client.get(explore), data['title'])

    def test_seed_catalog_is_affordable_preowned_and_relevant(self):
        from .import_catalog import SEED_CATALOG, localize_product
        categories = set()
        freebies = 0
        for index in range(100):
            data = localize_product({'id': index + 1, 'category': 'mens-shirts', 'title': 'Shirt'}, index)
            categories.add(data['category'])
            self.assertIn(data['condition'], ('like_new', 'good', 'fair'))
            self.assertIn('Depok', data['location'])
            if data['listing_type'] == 'free':
                self.assertIsNone(data['price'])
                freebies += 1
                continue
            if data['category'] == 'fashion':
                low, high = 10000, 150000
            elif data['category'] in ('books', 'accessories'):
                low, high = 10000, 200000
            elif data['category'] == 'home':
                low, high = 20000, 400000
            elif data['title'].startswith(('Laptop', 'Monitor')):
                low, high = 1000000, 5000000
            else:
                low, high = 30000, 500000
            self.assertGreaterEqual(data['price'], low)
            self.assertLessEqual(data['price'], high)
        self.assertEqual(categories, set(Item.Category.values))
        self.assertGreater(freebies, 0)
        for title, category in [('Rolex Watch', 'mens-watches'), ('Amazon Echo Plus', 'mobile-accessories'), ('Luxury Bag', 'womens-bags'), ('Wooden Bathroom Sink With Mirror', 'furniture'), ('Car', 'vehicle'), ('Lipstick', 'beauty')]:
            self.assertIsNone(localize_product({'id': 999, 'title': title, 'category': category}))
        self.assertNotIn('Baru', Item.Condition.labels)

    def test_one_hundred_distinct_local_catalog_photos(self):
        import hashlib
        from pathlib import Path
        from django.contrib.staticfiles import finders
        from .import_catalog import catalog_photos, localize_product
        photos = catalog_photos()
        self.assertEqual(len(photos), 100)
        self.assertEqual(len({photo['image_url'] for photo in photos}), 100)
        self.assertEqual(len({photo['original_url'] for photo in photos}), 100)
        hashes = set()
        for index, photo in enumerate(photos):
            relative = photo['image_url'].removeprefix('/static/')
            path = finders.find(relative)
            self.assertIsNotNone(path)
            data = Path(path).read_bytes()
            self.assertEqual(data[:4], b'RIFF')
            self.assertEqual(data[8:12], b'WEBP')
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest, photo['sha256'])
            hashes.add(digest)
            self.assertIn(photo['license'], ('by', 'by-sa', 'cc0', 'pdm'))
            self.assertTrue(photo['source_url'].startswith('https://'))
            localized = localize_product({'id': index+1, 'category': 'mens-shirts', 'title': 'Shirt'}, index)
            self.assertEqual(localized['image_url'], photo['image_url'])
            self.assertEqual(localized['title'], photo['title'])
        self.assertEqual(len(hashes), 100)

    def test_seed_photo_rendering_fallback_and_manual_photo_validation(self):
        from .validators import validate_item_image
        from django.core.exceptions import ValidationError
        local = '/static/img/items/catalog/item-001.webp'
        validate_item_image(local)
        for invalid in ('/static/img/items/catalog/../secret.webp', 'javascript:alert(1)', '/other/image.webp'):
            with self.assertRaises(ValidationError):
                validate_item_image(invalid)
        self.assertFalse(ItemForm({**self.data, 'image_url': local}).is_valid())
        seed = Item.objects.create(**{**self.data, 'image_url': local}, source='dummyjson', external_id=1)
        response = self.client.get(seed.get_absolute_url())
        self.assertContains(response, local)
        self.assertContains(response, 'data-fallback="/static/img/items/placeholder-fashion.svg"')
        self.assertContains(response, 'js/items/images.js')
        self.assertEqual(self.item.display_image_url, self.data['image_url'])
