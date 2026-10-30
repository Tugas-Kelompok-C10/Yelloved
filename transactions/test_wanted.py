from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from item_matching.models import ItemOffer
from item_matching.services import accept_offer
from wanted_board.models import WantedPost
from .models import Transaction
from .wanted import update_handover


class WantedTransactionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user('wanted_buyer')
        self.seller = User.objects.create_user('wanted_seller')
        self.other = User.objects.create_user('stranger')
        self.post = WantedPost.objects.create(requester=self.buyer, title='Book', budget=100000, location='UI')
        self.offer = ItemOffer.objects.create(wanted_post=self.post, offerer=self.seller,
                                               offered_price=Decimal('75000'), message='My book', photo='item_offers/test.jpg')

    def accept(self):
        accept_offer(self.offer.pk, self.buyer)
        return Transaction.objects.get(accepted_offer=self.offer)

    def test_accept_snapshots_price_parties_and_is_idempotent(self):
        order = self.accept()
        accept_offer(self.offer.pk, self.buyer)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(order.buyer_id, self.buyer.pk)
        self.assertEqual(order.seller_id, self.seller.pk)
        self.assertEqual(order.total_amount, Decimal('75000'))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'matched')
        for user in (self.buyer, self.seller):
            self.client.force_login(user)
            response = self.client.get(reverse('transactions:wanted_detail', args=[order.order_id]))
            self.assertContains(response, 'Transaction Detail')
            self.assertContains(self.client.get(reverse('item_matching:dashboard') + '?tab=' + ('offers_received' if user == self.buyer else 'offers_sent')), 'Continue to Transaction')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('transactions:wanted_detail', args=[order.order_id])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            update_handover(order.order_id, self.other, 'cancel')

    def test_failed_order_creation_rolls_back_acceptance(self):
        with patch('item_matching.services.Transaction.objects.create', side_effect=RuntimeError('storage unavailable')):
            with self.assertRaises(RuntimeError):
                accept_offer(self.offer.pk, self.buyer)
        self.offer.refresh_from_db(); self.post.refresh_from_db()
        self.assertEqual(self.offer.status, 'pending')
        self.assertEqual(self.post.status, 'open')

    def test_meetup_completion_fulfills_only_after_receipt(self):
        order = self.accept()
        with self.assertRaises(ValidationError):
            update_handover(order.order_id, self.buyer, 'complete')
        update_handover(order.order_id, self.buyer, 'meetup', {'location': 'UI Library', 'time': timezone.now() + timedelta(days=1)})
        with self.assertRaises(PermissionDenied):
            update_handover(order.order_id, self.seller, 'complete')
        update_handover(order.order_id, self.buyer, 'complete')
        order.refresh_from_db(); self.post.refresh_from_db()
        self.assertEqual((order.transaction_status, order.payment_status, self.post.status), ('completed', 'paid', 'fulfilled'))
        with self.assertRaises(ValidationError):
            update_handover(order.order_id, self.seller, 'cancel')

    def test_cancel_reopens_without_reviving_other_offers(self):
        rival = ItemOffer.objects.create(wanted_post=self.post, offerer=self.other, offered_price=50000)
        order = self.accept()
        update_handover(order.order_id, self.seller, 'cancel')
        self.post.refresh_from_db(); self.offer.refresh_from_db(); rival.refresh_from_db()
        self.assertEqual(self.post.status, 'open')
        self.assertEqual(self.offer.status, 'cancelled')
        self.assertEqual(rival.status, 'rejected')

    def test_confirmation_validation_and_status_delete_bypass(self):
        order = self.accept()
        self.client.force_login(self.buyer)
        url = reverse('transactions:wanted_detail', args=[order.order_id])
        response = self.client.post(url, {'action': 'complete'})
        self.assertContains(response, 'Please confirm this action')
        response = self.client.post(url, {'action': 'meetup', 'location': 'UI', 'time': '2000-01-01T10:00'})
        self.assertContains(response, 'Choose a meetup time in the future')
        response = self.client.post(reverse('wanted_board:delete_wanted', args=[self.post.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 409)
        self.client.post(reverse('wanted_board:update_status', args=[self.post.pk]), {'status': 'open'})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'matched')

    def test_legacy_accepted_offers_gain_an_order_once(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        self.offer.status = 'accepted'; self.offer.save()
        self.post.status = 'fulfilled'; self.post.save()
        migrate = import_module('transactions.migrations.0007_link_existing_accepted_offers').link_existing
        migrate(apps, SimpleNamespace(connection=connection))
        migrate(apps, SimpleNamespace(connection=connection))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'matched')
        self.assertEqual(Transaction.objects.filter(accepted_offer=self.offer).count(), 1)
