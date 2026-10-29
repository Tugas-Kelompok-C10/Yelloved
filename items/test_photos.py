from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ItemForm
from .models import Item, ItemImage


def photo(name='photo.jpg', format='JPEG'):
    content = BytesIO()
    Image.new('RGB', (24, 24), '#aedae7').save(content, format=format)
    return SimpleUploadedFile(name, content.getvalue(), content_type='image/' + format.lower())


class ItemPhotoTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = get_user_model().objects.create_user(username='multi_photo_owner')
        self.other = get_user_model().objects.create_user(username='multi_photo_other')
        self.client.force_login(self.owner)
        self.data = dict(title='Lampu kos', description='Real user description', category='electronics',
                         condition='good', price='54000', listing_type='sale', location='Kukusan, Depok')
        self.create = reverse('items:item_create')

    def create_item(self, count=2):
        response = self.client.post(self.create, {**self.data, 'images': [photo(f'{n}.jpg') for n in range(count)]})
        self.assertEqual(response.status_code, 302)
        return Item.objects.get(owner=self.owner)

    def test_create_multiple_primary_catalogue_detail_and_ignored_status(self):
        response = self.client.get(self.create)
        self.assertContains(response, 'name="images"')
        self.assertContains(response, 'multiple')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, 'name="status"')
        self.assertContains(response, 'Item photos')
        response = self.client.post(self.create, {**self.data, 'status': 'sold', 'owner': self.other.pk,
                                                'images': [photo(), photo('second.png', 'PNG')]})
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(owner=self.owner)
        self.assertEqual(item.status, 'available')
        images = list(item.images.all())
        self.assertEqual(len(images), 2)
        self.assertEqual(item.display_image_url, images[0].image.url)
        self.assertEqual(item.image.name, images[0].image.name)
        self.assertContains(self.client.get(reverse('items:explore_items')), images[0].image.url)
        detail = self.client.get(item.get_absolute_url())
        self.assertContains(detail, images[0].image.url)
        self.assertContains(detail, images[1].image.url)
        self.assertContains(detail, 'data-gallery-src')

    def test_placeholder_create_and_delete_all_photos(self):
        response = self.client.post(self.create, {**self.data, 'status': 'unavailable'})
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(owner=self.owner)
        self.assertEqual(item.status, 'available')
        self.assertFalse(item.has_image)
        self.assertEqual(item.display_image_url, item.fallback_image_url)
        edit = reverse('items:item_update', args=[item.pk])
        self.client.post(edit, {**self.data, 'status': 'available', 'images': [photo()]})
        image = item.images.get()
        self.client.post(edit, {**self.data, 'status': 'available', 'delete_images': [image.pk]})
        item.refresh_from_db()
        self.assertFalse(item.images.exists())
        self.assertFalse(item.image)
        self.assertEqual(item.display_image_url, item.fallback_image_url)

    def test_edit_remove_keep_add_and_owner_only_status(self):
        item = self.create_item()
        first, kept = item.images.all()
        edit = reverse('items:item_update', args=[item.pk])
        self.assertContains(self.client.get(edit), 'name="status"')
        response = self.client.post(edit, {**self.data, 'status': 'sold', 'delete_images': [first.pk],
                                          'images': [photo('new.webp', 'WEBP')]})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, 'sold')
        self.assertEqual(item.images.count(), 2)
        self.assertFalse(ItemImage.objects.filter(pk=first.pk).exists())
        self.assertEqual(item.display_image_url, kept.image.url)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(edit).status_code, 403)
        self.assertEqual(self.client.post(edit, {**self.data, 'status': 'available', 'delete_images': [kept.pk]}).status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.status, 'sold')
        self.assertTrue(ItemImage.objects.filter(pk=kept.pk).exists())

    def test_limit_five_counts_remaining_and_allows_replacement(self):
        item = self.create_item(5)
        edit = reverse('items:item_update', args=[item.pk])
        response = self.client.post(edit, {**self.data, 'status': 'available', 'images': [photo('extra.jpg')]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('images', response.context['form'].errors)
        self.assertEqual(item.images.count(), 5)
        first = item.images.first()
        response = self.client.post(edit, {**self.data, 'status': 'available', 'delete_images': [first.pk], 'images': [photo('replacement.jpg')]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.images.count(), 5)

    def test_invalid_uploads_and_cross_item_deletion_are_rejected_atomically(self):
        for uploads in ([photo(f'{n}.jpg') for n in range(6)],
                        [SimpleUploadedFile('fake.jpg', b'not an image')],
                        [photo('renamed.jpg', 'GIF')],
                        [SimpleUploadedFile('huge.jpg', b'x' * (5 * 1024 * 1024 + 1))],
                        [photo('disallowed.gif', 'GIF')]):
            response = self.client.post(self.create, {**self.data, 'images': uploads})
            self.assertEqual(response.status_code, 200)
            self.assertIn('images', response.context['form'].errors)
            self.assertFalse(Item.objects.filter(owner=self.owner).exists())
        item = self.create_item(1)
        foreign = Item.objects.create(owner=self.other, **self.data)
        image = ItemImage.objects.create(item=foreign, image=photo())
        response = self.client.post(reverse('items:item_update', args=[item.pk]),
                                    {**self.data, 'status': 'available', 'delete_images': [image.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('delete_images', response.context['form'].errors)
        self.assertTrue(ItemImage.objects.filter(pk=image.pk).exists())
        self.assertEqual(item.images.count(), 1)


    def test_migration_preserves_existing_uploaded_primary_without_copying_file(self):
        from importlib import import_module
        from types import SimpleNamespace
        from pathlib import Path
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        legacy = Item.objects.create(owner=self.owner, image=photo('legacy.jpg'), **self.data)
        before = list(Path(self.media.name).rglob('*.*'))
        original_url = legacy.display_image_url
        state = MigrationExecutor(connection).loader.project_state([('items', '0009_itemimage')]).apps
        migration = import_module('items.migrations.0009_itemimage')
        for _ in range(2):
            migration.preserve_existing_uploads(state, SimpleNamespace(connection=connection))
        legacy.refresh_from_db()
        self.assertEqual(legacy.images.count(), 1)
        self.assertEqual(legacy.images.first().image.name, legacy.image.name)
        self.assertEqual(legacy.display_image_url, original_url)
        self.assertEqual(legacy.owner, self.owner)
        self.assertEqual(list(Path(self.media.name).rglob('*.*')), before)
