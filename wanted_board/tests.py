from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Offer, WantedPost


class WantedBoardModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.requester = user_model.objects.create_user(
            username="cindy",
            password="test-password",
        )
        self.offerer = user_model.objects.create_user(
            username="seller",
            password="test-password",
        )
        self.wanted_post = WantedPost.objects.create(
            requester=self.requester,
            title="Looking for a study lamp",
            description="Preferably compact and suitable for a dorm desk.",
            category=WantedPost.Category.HOME,
            budget=Decimal("150000.00"),
            location="Kukusan",
        )

    def test_wanted_post_defaults_to_open(self):
        self.assertEqual(self.wanted_post.status, WantedPost.Status.OPEN)
        self.assertEqual(str(self.wanted_post), "Looking for a study lamp")

    def test_offer_is_connected_to_post_and_user(self):
        offer = Offer.objects.create(
            wanted_post=self.wanted_post,
            offerer=self.offerer,
            message="I have one in good condition.",
            offered_price=Decimal("125000.00"),
        )

        self.assertEqual(self.wanted_post.offers.get(), offer)
        self.assertEqual(self.offerer.wanted_offers.get(), offer)

    def test_user_can_only_offer_once_per_post(self):
        Offer.objects.create(
            wanted_post=self.wanted_post,
            offerer=self.offerer,
            message="First offer",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Offer.objects.create(
                wanted_post=self.wanted_post,
                offerer=self.offerer,
                message="Second offer",
            )
