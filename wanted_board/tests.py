from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Offer, WantedPost
from .forms import WantedPostForm
from .creation import issue_creation_token
from .sample_data import DUMMYJSON_PRODUCTS_URL, SAMPLE_WANTED_POSTS


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
        self.assertFalse(hasattr(self.wanted_post, "listing_type"))
        self.assertFalse(hasattr(self.wanted_post, "preferred_condition"))
        self.assertIn(WantedPost.Category.SKINCARE, WantedPost.Category.values)
        self.assertIn(
            WantedPost.Category.KITCHEN_HOUSEWARE,
            WantedPost.Category.values,
        )
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
            budget=Decimal("90000.00"),
            location="Kampus UI",
        )

    def test_create_rejects_missing_zero_and_negative_budget(self):
        self.client.force_login(self.other_user)
        for budget in ("", "0", "-1000"):
            with self.subTest(budget=budget):
                response = self.client.post(reverse("wanted_board:create_wanted"), {
                    "title": "Desk lamp", "description": "A compact desk lamp.",
                    "category": "home", "location": "UI", "budget": budget,
                })
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Please enter a maximum budget greater than Rp0.")
                self.assertTrue(response.context["open_create_modal"])
                self.assertEqual(response.context["creation_form"]["title"].value(), "Desk lamp")
        self.assertFalse(WantedPost.objects.filter(requester=self.other_user).exists())

    def test_edit_invalid_budget_keeps_modal_open_and_does_not_save(self):
        self.client.force_login(self.owner)
        original_budget = self.wanted_post.budget
        for budget in ("", "0", "-1000"):
            with self.subTest(budget=budget):
                response = self.client.post(
                    reverse("wanted_board:edit_wanted", args=[self.wanted_post.pk]),
                    {"title": self.wanted_post.title, "description": self.wanted_post.description,
                     "category": self.wanted_post.category, "budget": budget},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Please enter a maximum budget greater than Rp0.")
                self.assertTrue(response.context["open_edit_modal"])
                self.wanted_post.refresh_from_db()
                self.assertEqual(self.wanted_post.budget, original_budget)

    def test_positive_budget_and_html_constraints(self):
        for budget in ("0.01", "1", "150000"):
            form = WantedPostForm({
                "title": "Desk lamp", "description": "A desk lamp.",
                "category": "home", "budget": budget,
            })
            self.assertTrue(form.is_valid(), form.errors)
            self.assertTrue(form.fields["budget"].required)
            self.assertIn('min="0.01"', str(form["budget"]))

    def test_board_lists_and_filters_posts(self):
        response = self.client.get(
            reverse("wanted_board:show_wanted"),
            {
                "q": "calculus",
                "category": WantedPost.Category.BOOKS,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.wanted_post.title)
        self.assertEqual(list(response.context["wanted_posts"]), [self.wanted_post])
        self.assertEqual(response.context["selected_category"], WantedPost.Category.BOOKS)
        self.assertNotContains(response, 'name="condition"')
        self.assertNotContains(response, 'name="listing_type"')

    def test_board_returns_filtered_card_markup_for_ajax_search(self):
        response = self.client.get(
            reverse("wanted_board:show_wanted"),
            {
                "q": "calculus",
                "category": WantedPost.Category.BOOKS,
            },
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_category"], WantedPost.Category.BOOKS)
        self.assertNotIn("selected_condition", payload)
        self.assertNotIn("selected_listing_type", payload)
        self.assertEqual(payload["result_label"], "1 request found")
        self.assertIn(self.wanted_post.title, payload["html"])
        self.assertNotIn("Casio Scientific Calculator", payload["html"])

    def test_board_paginates_real_and_sample_cards(self):
        response = self.client.get(reverse("wanted_board:show_wanted"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sample_posts"]), 30)
        self.assertContains(response, "Essence Mascara Lash Princess")
        self.assertContains(response, "Annibale Colombo Bed")
        self.assertNotContains(response, "Cooking Oil")
        self.assertNotContains(response, "Kiwi")
        self.assertContains(response, "data-sample-card", count=11)
        self.assertEqual(len(response.context["wanted_cards"]), 12)
        self.assertContains(response, 'aria-label="Next page"')
        self.assertNotContains(response, "See More")
        self.assertNotContains(response, "requests found")

        second_page = self.client.get(reverse("wanted_board:show_wanted"), {"page": 3})
        self.assertContains(second_page, "Kiwi")
        self.assertNotContains(second_page, self.wanted_post.title)
        self.assertEqual(len(second_page.context["wanted_cards"]), 7)
        self.assertEqual(second_page.context["total_count"], 31)

    def test_ajax_pagination_preserves_filters_and_handles_invalid_pages(self):
        url = reverse("wanted_board:show_wanted")
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.get(url, {"page": 2}, **headers)
        self.assertEqual(response.json()["page_number"], 2)
        self.assertIn(SAMPLE_WANTED_POSTS[11]["title"], response.json()["html"])
        self.assertIn('aria-current="page"', response.json()["pagination_html"])
        for page, expected in (("invalid", 1), ("999", 3), ("-1", 3)):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(url, {"page": page}, **headers).json()["page_number"], expected)
        filtered = self.client.get(url, {"q": "calculus", "category": "books", "page": 2}, **headers).json()
        self.assertEqual(filtered["page_number"], 1)
        self.assertIn(self.wanted_post.title, filtered["html"])
        self.assertEqual(filtered["pagination_html"].count('aria-disabled="true"'), 2)
        empty = self.client.get(url, {"q": "no-such-wanted-item"}, **headers).json()
        self.assertIn("No matching wanted posts", empty["html"])
        self.assertEqual(empty["page_number"], 1)

    def test_sample_card_has_a_detail_page(self):
        response = self.client.get(
            reverse(
                "wanted_board:sample_wanted_detail",
                args=["dummyjson-1-essence-mascara-lash-princess"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Essence Mascara Lash Princess")
        self.assertContains(response, "9 October 2025")
        self.assertContains(response, "Fasilkom UI")
        self.assertContains(response, "Skincare")
        self.assertContains(response, "Rp 160.000")
        self.assertContains(response, "Got this item?")
        self.assertContains(response, "@Essence")
        self.assertContains(
            response,
            reverse("chat:inbox"),
        )
        self.assertNotContains(response, "wanted-detail-media")

    def test_sample_data_uses_all_30_dummyjson_products(self):
        self.assertEqual(DUMMYJSON_PRODUCTS_URL, "https://dummyjson.com/products?limit=30")
        self.assertEqual(len(SAMPLE_WANTED_POSTS), 30)
        self.assertEqual(
            {post["source_id"] for post in SAMPLE_WANTED_POSTS},
            set(range(1, 31)),
        )
        self.assertTrue(
            all(post["source"] == "DummyJSON" for post in SAMPLE_WANTED_POSTS)
        )

    def test_detail_displays_explore_style_information_and_formatted_budget(self):
        response = self.client.get(
            reverse("wanted_board:wanted_detail", args=[self.wanted_post.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Books &amp; Study")
        self.assertContains(response, "Kampus UI")
        self.assertContains(response, "Rp 90.000")
        self.assertContains(response, "Max budget")
        self.assertContains(response, "Got this item?")
        self.assertContains(response, "Chat")
        self.assertContains(response, "@owner")
        self.assertContains(
            response,
            reverse("chat:with_user", args=[self.owner.pk]),
        )
        self.assertNotContains(response, ">Buy</a>")
        self.assertNotContains(response, "<dt>Status</dt>", html=True)

    def test_detail_has_inline_offer_form_with_disabled_submit(self):
        self.client.login(username="other", password="test-password")

        response = self.client.get(
            reverse("wanted_board:wanted_detail", args=[self.wanted_post.pk])
        )

        self.assertContains(response, "Got this item?")
        self.assertNotContains(response, 'id="item-offer-modal"')
        self.assertContains(response, 'name="image"')
        self.assertContains(response, 'name="price"')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, "Send offer")
        self.assertContains(response, 'data-send-item-offer disabled')
        self.assertNotContains(response, 'data-open-item-offer-modal')
        self.assertContains(response, 'data-offer-url-template=')
        self.assertContains(response, 'name="submission_id"')

    def test_board_offer_buttons_are_separate_from_detail_links(self):
        response = self.client.get(reverse("wanted_board:show_wanted"))
        self.assertContains(response, 'id="item-offer-modal"', count=1)
        self.assertContains(response, '<button class="wanted-card-cta"', count=12)
        self.assertContains(response, f'data-offer-title="{self.wanted_post.title}"')
        self.assertContains(response, 'data-send-item-offer disabled')
        self.client.force_login(self.owner)
        owned = self.client.get(reverse("wanted_board:show_wanted"))
        self.assertContains(owned, '>Manage post</a>')
        self.assertContains(owned, '<span class="wanted-yours-stamp">Yours!</span>', count=1, html=True)

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
                "creation_token": issue_creation_token(self.other_user),
                "description": "Need a compact chair for a dorm room.",
                "category": WantedPost.Category.HOME,
                "budget": "200000",
                "location": "Margonda",
            },
        )

        created_post = WantedPost.objects.get(title="Desk chair")
        self.assertRedirects(
            response,
            reverse("wanted_board:wanted_detail", args=[created_post.pk]),
        )
        self.assertEqual(created_post.requester, self.other_user)

    def test_wanted_post_and_create_form_have_no_image_field(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("wanted_board:show_wanted"))
        self.assertNotIn("image", response.context["creation_form"].fields)
        self.assertNotIn("image", {field.name for field in WantedPost._meta.fields})
        self.assertNotIn('type="file"', str(response.context["creation_form"]))

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
        self.assertContains(invalid_response, "Your location")
        self.assertContains(invalid_response, ">Save</button>")
        self.assertNotContains(invalid_response, "Save wanted post")
        self.assertNotContains(
            invalid_response,
            '<span class="wanted-eyebrow">Wanted Board</span>',
        )
        self.assertFalse(WantedPost.objects.filter(requester=self.other_user).exists())

    def test_create_rejects_item_name_longer_than_50_characters(self):
        self.client.login(username="other", password="test-password")

        response = self.client.post(
            reverse("wanted_board:create_wanted"),
            {
                "title": "A" * 51,
                "description": "A valid description for the requested item.",
                "category": WantedPost.Category.OTHER,
                "budget": "100000",
                "location": "Kampus UI",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Ensure this value has at most 50 characters (it has 51).",
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
        detail_response = self.client.get(
            reverse("wanted_board:wanted_detail", args=[self.wanted_post.pk])
        )

        self.assertContains(detail_response, ">Edit</button>")
        self.assertContains(detail_response, 'id="edit-wanted-modal"')
        self.assertContains(detail_response, 'id="delete-wanted-modal"')
        self.assertContains(detail_response, ">Save</button>")
        self.assertNotContains(detail_response, "Mark as fulfilled")
        self.assertNotContains(detail_response, "Suggested items")
        self.assertNotContains(detail_response, "Incoming offers")
        self.assertNotContains(detail_response, "Offer an Item")
        self.assertNotContains(detail_response, ">Chat</a>")

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
        self.assertEqual(offer.message, "")

    def test_offer_requires_a_price(self):
        self.client.login(username="other", password="test-password")

        self.client.post(
            reverse("wanted_board:create_offer", args=[self.wanted_post.pk]),
            {},
        )

        self.assertFalse(Offer.objects.exists())

    def test_owner_and_duplicate_offer_are_rejected(self):
        offer_url = reverse(
            "wanted_board:create_offer",
            args=[self.wanted_post.pk],
        )
        payload = {"offered_price": "75000"}

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
            reverse("wanted_board:delete_wanted", args=[self.wanted_post.pk]),
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("wanted_board:show_wanted"),
            status_code=302,
            target_status_code=200,
        )
        self.assertContains(response, "Your wanted post has been deleted.")
        self.assertContains(response, 'data-toast-duration="3000"')
        self.assertFalse(WantedPost.objects.filter(pk=self.wanted_post.pk).exists())
