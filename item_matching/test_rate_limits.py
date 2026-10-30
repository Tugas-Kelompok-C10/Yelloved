import io
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from wanted_board.models import WantedPost
from .models import ItemOffer, PhotoOfferQuota, PhotoOfferSendEvent
from .views import photo_offer_create


def payload(token=None):
    image = io.BytesIO()
    Image.new('RGB', (10, 10)).save(image, 'PNG')
    return {'submission_id': token or uuid.uuid4(), 'price': '10000', 'description': 'Lamp, pickup at UI.',
            'image': SimpleUploadedFile('lamp.png', image.getvalue(), 'image/png')}


class PhotoOfferRateTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='photo-rate-owner')
        self.sender = get_user_model().objects.create_user(username='photo-rate-sender')
        self.post = WantedPost.objects.create(requester=self.owner, title='Lamp', budget=10000)
        self.client.force_login(self.sender)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        storage = patch.object(ItemOffer._meta.get_field('photo'), 'storage', FileSystemStorage(location=self.folder.name))
        storage.start()
        self.addCleanup(storage.stop)

    def send(self, token=None, **changes):
        return self.client.post(reverse('item_matching:photo_offer_create', args=[self.post.pk]),
                                {**payload(token), **changes}, HTTP_X_OFFER_USER=str(self.sender.pk))

    def fill(self):
        responses = [self.send() for _ in range(5)]
        self.assertTrue(all(response.status_code == 201 for response in responses))

    def test_five_offers_allowed_then_429_without_saving_another_photo(self):
        self.fill()
        response = self.send()
        self.assertEqual(response.status_code, 429)
        self.assertIn('5 photo offers in 10 minutes', response.json()['message'])
        self.assertEqual(int(response['Retry-After']), response.json()['retry_after'])
        self.assertTrue(1 <= response.json()['retry_after'] <= 600)
        self.assertEqual(PhotoOfferSendEvent.objects.count(), 5)
        self.assertEqual(ItemOffer.objects.count(), 5)
        self.assertEqual(len(ItemOffer._meta.get_field('photo').storage.listdir('item_offers')[1]), 5)

    def test_retry_at_limit_returns_existing_offer_without_consuming_slot(self):
        self.fill()
        token = ItemOffer.objects.first().submission_id
        self.assertEqual(self.send(token).status_code, 200)
        self.assertEqual(PhotoOfferSendEvent.objects.count(), 5)

    def test_post_deletion_does_not_reset_limit_but_expiry_does(self):
        self.fill()
        self.post.delete()
        self.post = WantedPost.objects.create(requester=self.owner, title='Another lamp', budget=10000)
        self.assertEqual(self.send().status_code, 429)
        PhotoOfferSendEvent.objects.update(created_at=timezone.now() - timedelta(minutes=10))
        self.assertEqual(self.send().status_code, 201)
        self.assertEqual(PhotoOfferSendEvent.objects.count(), 1)

    def test_invalid_form_and_storage_failure_consume_no_slot(self):
        self.assertEqual(self.send(price='-1').status_code, 422)
        storage = ItemOffer._meta.get_field('photo').storage
        with patch.object(storage, 'save', side_effect=OSError('Disk full')):
            self.assertEqual(self.send().status_code, 503)
        self.assertFalse(PhotoOfferSendEvent.objects.exists())
        self.assertFalse(ItemOffer.objects.exists())
        self.assertEqual(self.send().status_code, 201)

    def test_other_accounts_have_independent_limits(self):
        self.fill()
        self.sender = get_user_model().objects.create_user(username='another-photo-rate-sender')
        self.client.force_login(self.sender)
        self.assertEqual(self.send().status_code, 201)


class ConcurrentPhotoOfferRateTests(TransactionTestCase):
    def test_parallel_offers_to_different_posts_share_one_account_limit(self):
        database = str(connection.settings_dict['NAME'])
        if connection.vendor == 'sqlite' and (database == ':memory:' or 'mode=memory' in database):
            self.skipTest('Concurrent SQLite writes require a file-backed test database.')
        owner = get_user_model().objects.create_user(username='parallel-photo-owner')
        sender = get_user_model().objects.create_user(username='parallel-photo-sender')
        posts = [WantedPost.objects.create(requester=owner, title=f'Lamp {n}', budget=10000) for n in range(2)]
        quota = PhotoOfferQuota.objects.create(user=sender)
        for _ in range(4): quota.events.create()
        barrier = threading.Barrier(2)
        with tempfile.TemporaryDirectory() as folder, patch.object(ItemOffer._meta.get_field('photo'), 'storage', FileSystemStorage(location=folder)):
            def send(post):
                try:
                    request = RequestFactory().post('/offers/', payload(), HTTP_X_OFFER_USER=str(sender.pk))
                    request.user = sender
                    barrier.wait(timeout=10)
                    return photo_offer_create(request, post.pk).status_code
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertCountEqual(list(pool.map(send, posts)), [201, 429])
            self.assertEqual(len(ItemOffer._meta.get_field('photo').storage.listdir('item_offers')[1]), 1)
        self.assertEqual(PhotoOfferSendEvent.objects.count(), 5)
        self.assertEqual(ItemOffer.objects.count(), 1)
