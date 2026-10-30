import io
import tempfile
import uuid
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from wanted_board.models import WantedPost
from .models import ItemOffer
from . import services


class PhotoOfferTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='offer-owner')
        self.sender = User.objects.create_user(username='offer-sender')
        self.stranger = User.objects.create_user(username='offer-stranger')
        self.post = WantedPost.objects.create(requester=self.owner, title='Study lamp', description='A small lamp', budget=150000)
        self.url = reverse('item_matching:photo_offer_create', args=[self.post.pk])
        self.client.force_login(self.sender)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        storage = patch.object(ItemOffer._meta.get_field('photo'), 'storage', FileSystemStorage(location=directory.name))
        storage.start(); self.addCleanup(storage.stop)

    def send(self, token=None, **changes):
        image = io.BytesIO(); Image.new('RGB', (10, 10)).save(image, 'PNG')
        data = {'submission_id': token or uuid.uuid4(), 'image': SimpleUploadedFile('lamp.png', image.getvalue(), 'image/png'),
                'price': '70000', 'description': 'Working lamp, pickup at UI Library.'}
        data.update(changes)
        return self.client.post(self.url, data, HTTP_X_OFFER_USER=str(self.client.session['_auth_user_id']))

    def test_photo_offer_visible_to_recipient_and_sender_and_preview(self):
        self.assertEqual(self.send().status_code, 201)
        offer = ItemOffer.objects.get()
        self.assertIsNone(offer.item_id)
        self.assertTrue(offer.photo.storage.exists(offer.photo.name))
        self.assertEqual(offer.price_display, 'Rp70.000')
        sent = self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_sent'})
        self.assertContains(sent, 'Working lamp')
        self.assertContains(sent, 'Rp70.000')
        self.client.force_login(self.owner)
        incoming = self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_received'})
        self.assertContains(incoming, 'offer-sender')
        self.assertContains(incoming, 'Working lamp')
        preview = self.client.get(reverse('item_matching:activity_preview')).json()
        self.assertEqual(preview['pending'], 1)
        self.assertIn('Incoming Offers', preview['html'])
        self.client.force_login(self.stranger)
        self.assertNotContains(self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_received'}), 'Working lamp')

    def test_same_submission_retries_do_not_duplicate_files_or_offers(self):
        token = uuid.uuid4()
        self.assertEqual(self.send(token).status_code, 201)
        self.assertEqual(self.send(token).status_code, 200)
        self.assertEqual(ItemOffer.objects.count(), 1)
        storage = ItemOffer._meta.get_field('photo').storage
        self.assertEqual(len(storage.listdir('item_offers')[1]), 1)

    def test_required_fields_image_and_price_are_validated(self):
        for changes in ({'image': ''}, {'image': SimpleUploadedFile('fake.png', b'bad')}, {'price': '-1'},
                        {'price': ''}, {'description': ' '}, {'description': 'x' * 241}):
            with self.subTest(changes=list(changes)):
                self.assertEqual(self.send(**changes).status_code, 422)
        self.assertFalse(ItemOffer.objects.exists())

    def test_owner_closed_post_and_account_change_are_rejected(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.send().status_code, 403)
        self.client.force_login(self.sender)
        self.post.status = WantedPost.Status.CLOSED; self.post.save()
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(self.client.post(self.url, {}, HTTP_X_OFFER_USER='wrong').status_code, 409)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 401)

    def test_photo_offer_accept_reject_and_withdraw_use_existing_rules(self):
        self.send(); offer = ItemOffer.objects.get()
        with self.assertRaises(services.MatchingError): services.accept_offer(offer.pk, self.stranger)
        services.accept_offer(offer.pk, self.owner)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, WantedPost.Status.MATCHED)
        self.client.force_login(self.sender)
        self.assertContains(self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_sent'}), 'Chat')
