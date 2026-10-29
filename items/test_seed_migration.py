from importlib import import_module
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.urls import reverse

from .models import Item

seed = import_module('items.migrations.0008_seed_catalogue_items')


class CatalogueSeedMigrationTests(TestCase):
    def setUp(self):
        self.apps = MigrationExecutor(connection).loader.project_state([
            ('items', '0008_seed_catalogue_items'),
        ]).apps
        self.editor = SimpleNamespace(connection=connection)
        self.ids = [row[0] for row in seed.SEED_ITEMS]

    def test_migrate_installs_twenty_offline_demo_items(self):
        items = Item.objects.filter(external_id__in=self.ids)
        self.assertEqual(items.count(), 20)
        self.assertEqual(len(set(self.ids)), 20)
        seller = get_user_model().objects.get(username=seed.DEMO_USERNAME)
        self.assertEqual(seller.get_full_name(), 'Yelloved Community')
        self.assertFalse(seller.has_usable_password())
        self.assertFalse(seller.is_staff)
        self.assertEqual(items.filter(owner=seller, status='available', currency='IDR').count(), 20)
        self.assertTrue(items.filter(listing_type='free').exists())
        for item in items:
            self.assertTrue(item.is_catalog)
            self.assertIn(item.condition, ('like_new', 'good', 'fair'))
            self.assertTrue((Path(settings.BASE_DIR) / item.image_url.removeprefix('/')).is_file())
            self.assertEqual(item.source, 'user')  # Existing matching contract.
            self.assertLessEqual(item.price or 0, 150000)
        # Forward replay is deterministic and must never need the Public API.
        with patch('requests.get', side_effect=AssertionError('No network in migration')):
            seed.seed_catalogue(self.apps, self.editor)
        self.assertEqual(items.count(), 20)
        viewer = get_user_model().objects.create_user(username='seed_viewer')
        self.client.force_login(viewer)
        item = items.filter(listing_type='sale').first()
        self.assertTrue(self.client.get(item.get_absolute_url()).context['can_request_item'])
        self.assertTrue(self.client.post(reverse('items:toggle_favorite', args=[item.pk])).json()['is_favorited'])
        response = self.client.post(reverse('item_matching:request_create', args=[item.pk]),
                                    {'offer_price': '20000', 'message': 'Demo request'})
        self.assertRedirects(response, reverse('item_matching:dashboard') + '?tab=sent',
                             fetch_redirect_response=False)

    def test_reverse_preserves_manual_and_other_imported_items_and_seller(self):
        owner = get_user_model().objects.create_user(username='real_seed_owner')
        manual = Item.objects.create(owner=owner, title='Manual listing', category='books',
                                     condition='good', listing_type='free')
        seller = get_user_model().objects.get(username=seed.DEMO_USERNAME)
        other_import = Item.objects.create(owner=seller, title='Earlier API import', external_id=222,
                                           category='books', condition='good', listing_type='free')
        seed.unseed_catalogue(self.apps, self.editor)
        self.assertFalse(Item.objects.filter(external_id__in=self.ids).exists())
        self.assertEqual(Item.objects.get(pk=manual.pk).owner, owner)
        self.assertTrue(Item.objects.filter(pk=other_import.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=seller.pk).exists())
        seed.unseed_catalogue(self.apps, self.editor)
        seed.seed_catalogue(self.apps, self.editor)
        self.assertEqual(Item.objects.filter(external_id__in=self.ids).count(), 20)

    def test_seed_collisions_never_overwrite_manual_item_or_demo_account(self):
        seed.unseed_catalogue(self.apps, self.editor)
        owner = get_user_model().objects.create_user(username='collision_owner')
        manual = Item.objects.create(owner=owner, external_id=self.ids[0], title='Manual collision',
                                     category='books', condition='good', listing_type='free')
        with self.assertRaises(RuntimeError), transaction.atomic():
            seed.seed_catalogue(self.apps, self.editor)
        manual.refresh_from_db()
        self.assertEqual(manual.owner, owner)
        self.assertEqual(manual.title, 'Manual collision')
        seed.unseed_catalogue(self.apps, self.editor)
        self.assertTrue(Item.objects.filter(pk=manual.pk).exists())
        manual.delete()
        seller = get_user_model().objects.get(username=seed.DEMO_USERNAME)
        seller.set_password('real-account-password')
        seller.save()
        with self.assertRaises(RuntimeError), transaction.atomic():
            seed.seed_catalogue(self.apps, self.editor)
        seller.refresh_from_db()
        self.assertTrue(seller.check_password('real-account-password'))
        self.assertFalse(Item.objects.filter(external_id__in=self.ids).exists())

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_api_refresh_preserves_the_twenty_migration_seeds(self, get):
        get.return_value.json.return_value = {'products': [
            {'id': n, 'title': 'Shirt', 'category': 'mens-shirts', 'price': 10}
            for n in range(1, 51)
        ]}
        call_command('import_dummyjson_items', limit=50, refresh=True, stdout=StringIO())
        self.assertEqual(Item.objects.filter(external_id__in=self.ids).count(), 20)
        self.assertEqual(Item.objects.count(), 70)
