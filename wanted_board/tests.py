from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

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


class WantedBoardViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner",
            password="test-password",
        )
        self.other_user = user_model.objects.create_user(
            username="other",
            password="test-password",
        )
        self.wanted_post = WantedPost.objects.create(
            requester=self.owner,
            title="Used calculus textbook",
            description="Looking for a clean copy with no missing pages.",
            category=WantedPost.Category.BOOKS,
            preferred_condition=WantedPost.Condition.GOOD,
            budget=Decimal("90000.00"),
            location="Kampus UI",
        )

    def test_board_lists_and_filters_posts(self):
        response = self.client.get(
            reverse("wanted_board:show_wanted"),
            {"q": "calculus", "category": WantedPost.Category.BOOKS},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.wanted_post.title)
        self.assertEqual(list(response.context["wanted_posts"]), [self.wanted_post])

    def test_board_returns_filtered_card_markup_for_ajax_search(self):
        response = self.client.get(
            reverse("wanted_board:show_wanted"),
            {"q": "calculus", "category": WantedPost.Category.BOOKS},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_category"], WantedPost.Category.BOOKS)
        self.assertEqual(payload["result_label"], "1 request found")
        self.assertIn(self.wanted_post.title, payload["html"])
        self.assertNotIn("Casio Scientific Calculator", payload["html"])

    def test_board_includes_eight_sample_cards(self):
        response = self.client.get(reverse("wanted_board:show_wanted"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sample_posts"]), 8)
        self.assertContains(response, "Casio Scientific Calcula…")
        self.assertContains(response, "Mini Rice Cooker")
        self.assertContains(response, "Portable Laptop Stand")
        self.assertContains(response, "Canvas Tote Bag")
        self.assertContains(response, "data-sample-card", count=8)

    def test_sample_card_has_a_detail_page(self):
        response = self.client.get(
            reverse(
                "wanted_board:sample_wanted_detail",
                args=["casio-scientific-calculator"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Casio Scientific Calculator")
        self.assertContains(response, "Nadia Putri")
        self.assertContains(response, "Good")
        self.assertContains(response, "Fasilkom UI")

    def test_create_requires_login_and_assigns_requester(self):
        create_url = reverse("wanted_board:create_wanted")
        anonymous_response = self.client.get(create_url)
        self.assertRedirects(
            anonymous_response,
            f"{reverse('login')}?next={create_url}",
        )

        self.client.login(username="other", password="test-password")
        response = self.client.post(
            create_url,
            {
                "title": "Desk chair",
                "image": SimpleUploadedFile(
                    "desk-chair.png",
                    b"reference-image",
                    content_type="image/png",
                ),
                "description": "Need a compact chair for a dorm room.",
                "category": WantedPost.Category.HOME,
                "preferred_condition": WantedPost.Condition.ANY,
                "budget": "200000",
                "location": "Margonda",
            },
        )

        created_post = WantedPost.objects.get(title="Desk chair")
        self.addCleanup(created_post.image.delete, save=False)
        self.assertRedirects(
            response,
            reverse("wanted_board:wanted_detail", args=[created_post.pk]),
        )
        self.assertEqual(created_post.requester, self.other_user)
        self.assertTrue(created_post.image.name.endswith("desk-chair.png"))

    def test_create_requires_a_reference_image(self):
        self.client.login(username="other", password="test-password")

        response = self.client.post(
            reverse("wanted_board:create_wanted"),
            {
                "title": "Desk chair",
                "description": "Need a compact chair for a dorm room.",
                "category": WantedPost.Category.HOME,
                "preferred_condition": WantedPost.Condition.ANY,
                "budget": "200000",
                "location": "Margonda",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.context["creation_form"].errors)
        self.assertContains(response, "This picture is for reference only.")
        self.assertFalse(WantedPost.objects.filter(requester=self.other_user).exists())

    def test_create_form_opens_as_modal_and_keeps_validation_errors(self):
        self.client.login(username="other", password="test-password")
        create_url = reverse("wanted_board:create_wanted")

        get_response = self.client.get(create_url)
        self.assertRedirects(
            get_response,
            f"{reverse('wanted_board:show_wanted')}?create=1",
        )

        invalid_response = self.client.post(create_url, {})
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, 'id="create-wanted-modal"')
        self.assertContains(invalid_response, 'data-auto-open="true"')
        self.assertContains(invalid_response, "This field is required.")
        self.assertFalse(WantedPost.objects.filter(requester=self.other_user).exists())

    def test_create_rejects_item_name_longer_than_25_characters(self):
        self.client.login(username="other", password="test-password")

        response = self.client.post(
            reverse("wanted_board:create_wanted"),
            {
                "title": "A" * 26,
                "description": "A valid description for the requested item.",
                "category": WantedPost.Category.OTHER,
                "preferred_condition": WantedPost.Condition.ANY,
                "budget": "100000",
                "location": "Kampus UI",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Ensure this value has at most 25 characters (it has 26).",
        )
        self.assertFalse(WantedPost.objects.filter(requester=self.other_user).exists())

    def test_only_owner_can_edit_or_delete_post(self):
        self.client.login(username="other", password="test-password")

        edit_response = self.client.post(
            reverse("wanted_board:edit_wanted", args=[self.wanted_post.pk]),
            {
                "title": "Changed by someone else",
                "description": self.wanted_post.description,
                "category": self.wanted_post.category,
                "preferred_condition": self.wanted_post.preferred_condition,
            },
        )
        delete_response = self.client.post(
            reverse("wanted_board:delete_wanted", args=[self.wanted_post.pk])
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.wanted_post.refresh_from_db()
        self.assertEqual(self.wanted_post.title, "Used calculus textbook")

    def test_owner_can_update_post_status(self):
        self.client.login(username="owner", password="test-password")
        response = self.client.post(
            reverse("wanted_board:update_status", args=[self.wanted_post.pk]),
            {"status": WantedPost.Status.FULFILLED},
        )

        self.assertRedirects(
            response,
            reverse("wanted_board:wanted_detail", args=[self.wanted_post.pk]),
        )
        self.wanted_post.refresh_from_db()
        self.assertEqual(self.wanted_post.status, WantedPost.Status.FULFILLED)

    def test_other_user_can_offer_on_open_post(self):
        self.client.login(username="other", password="test-password")
        response = self.client.post(
            reverse("wanted_board:create_offer", args=[self.wanted_post.pk]),
            {
                "message": "I have a clean copy.",
                "offered_price": "75000",
            },
        )

        self.assertRedirects(
            response,
            reverse("wanted_board:wanted_detail", args=[self.wanted_post.pk]),
        )
        offer = Offer.objects.get(wanted_post=self.wanted_post)
        self.assertEqual(offer.offerer, self.other_user)
        self.assertEqual(offer.offered_price, Decimal("75000"))

    def test_owner_and_duplicate_offer_are_rejected(self):
        offer_url = reverse(
            "wanted_board:create_offer",
            args=[self.wanted_post.pk],
        )
        payload = {"message": "Offer message", "offered_price": "75000"}

        self.client.login(username="owner", password="test-password")
        self.client.post(offer_url, payload)
        self.assertFalse(Offer.objects.exists())

        self.client.login(username="other", password="test-password")
        self.client.post(offer_url, payload)
        self.client.post(offer_url, payload)
        self.assertEqual(Offer.objects.count(), 1)

    def test_owner_can_delete_post(self):
        self.client.login(username="owner", password="test-password")
        response = self.client.post(
            reverse("wanted_board:delete_wanted", args=[self.wanted_post.pk])
        )

        self.assertRedirects(response, reverse("wanted_board:show_wanted"))
        self.assertFalse(WantedPost.objects.filter(pk=self.wanted_post.pk).exists())
