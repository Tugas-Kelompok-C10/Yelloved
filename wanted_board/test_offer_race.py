from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.test import Client, TestCase
from django.urls import reverse

from .models import Offer, WantedPost


class WantedOfferRaceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="offer-owner")
        self.offerer = User.objects.create_user(username="offer-sender")
        self.post = WantedPost.objects.create(requester=self.owner, title="Lamp", budget=50000)
        self.url = reverse("wanted_board:create_offer", args=[self.post.pk])
        self.client.force_login(self.offerer)

    def test_repeated_submission_never_overwrites_original_offer(self):
        self.client.post(self.url, {"offered_price": 10000})
        response = self.client.post(self.url, {"offered_price": 20000}, follow=True)
        self.assertContains(response, "You have already made an offer on this post.")
        self.assertEqual(Offer.objects.count(), 1)
        self.assertEqual(Offer.objects.get().offered_price, 10000)

    def test_losing_insert_race_returns_existing_offer_instead_of_database_error(self):
        winner = Offer.objects.create(wanted_post=self.post, offerer=self.offerer, offered_price=10000)
        original_get = QuerySet.get
        lookups = []

        def lookup(queryset, *args, **kwargs):
            if queryset.model is Offer:
                lookups.append(kwargs)
                if len(lookups) == 1:
                    # The first request saw no row; another committed before its INSERT.
                    raise Offer.DoesNotExist
            return original_get(queryset, *args, **kwargs)

        with patch.object(QuerySet, "get", lookup):
            response = self.client.post(self.url, {"offered_price": 20000}, follow=True)
        self.assertContains(response, "You have already made an offer on this post.")
        self.assertEqual(len(lookups), 2)
        self.assertEqual(Offer.objects.count(), 1)
        winner.refresh_from_db()
        self.assertEqual(winner.offered_price, 10000)

    def test_different_users_can_offer_on_the_same_post(self):
        self.client.post(self.url, {"offered_price": 10000})
        other = get_user_model().objects.create_user(username="another-offerer")
        self.client.force_login(other)
        self.client.post(self.url, {"offered_price": 20000})
        self.assertEqual(Offer.objects.filter(wanted_post=self.post).count(), 2)

    def test_owner_and_closed_posts_still_reject_offers(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, {"offered_price": 10000})
        self.client.force_login(self.offerer)
        for status in (WantedPost.Status.CLOSED, WantedPost.Status.FULFILLED):
            self.post.status = status
            self.post.save()
            self.client.post(self.url, {"offered_price": 10000})
        self.assertFalse(Offer.objects.exists())

    def test_csrf_is_still_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.offerer)
        self.assertEqual(client.post(self.url, {"offered_price": 10000}).status_code, 403)
        self.assertFalse(Offer.objects.exists())

    def test_submitting_offer_does_not_change_posts_edit_revision(self):
        revision = self.post.updated_at
        self.client.post(self.url, {"offered_price": 10000})
        self.post.refresh_from_db()
        self.assertEqual(self.post.updated_at, revision)

    def test_database_failure_rolls_back_offer_transaction(self):
        with patch.object(Offer.objects, "get_or_create", side_effect=RuntimeError("Storage unavailable")):
            with self.assertRaisesMessage(RuntimeError, "Storage unavailable"):
                self.client.post(self.url, {"offered_price": 10000})
        self.assertFalse(Offer.objects.exists())
        # A failed transaction must release its lock and permit a later retry.
        self.assertEqual(self.client.post(self.url, {"offered_price": 10000}).status_code, 302)
        self.assertEqual(Offer.objects.count(), 1)
