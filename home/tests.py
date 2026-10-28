from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from items.models import Item
from wanted_board.models import WantedPost


class LandingPageTests(TestCase):
    def test_landing_renders_for_guests_with_explore_destination(self):
        response = self.client.get(reverse("show_main"))
        self.assertContains(response, "Give good things another love.")
        self.assertContains(response, reverse("items:explore_items"))
        self.assertEqual(response.context["heart_count"], 0)

    def test_ajax_hearts_increment_and_survive_page_reload(self):
        for expected in (1, 2, 3):
            response = self.client.post(reverse("send_love"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"count": expected})
        response = self.client.get(reverse("show_main"))
        self.assertEqual(response.context["heart_count"], 3)

    def test_heart_count_is_private_to_each_browser_session(self):
        self.client.post(reverse("send_love"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        another_browser = Client()
        self.assertEqual(another_browser.get(reverse("show_main")).context["heart_count"], 0)

    def test_heart_endpoint_requires_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(reverse("send_love")).status_code, 405)
        self.assertEqual(client.post(reverse("send_love")).status_code, 403)
        client.get(reverse("show_main"))
        csrf_token = client.cookies["csrftoken"].value
        response = client.post(reverse("send_love"), HTTP_X_CSRFTOKEN=csrf_token,
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"count": 1})

    def test_non_javascript_submission_redirects_back_to_landing(self):
        response = self.client.post(reverse("send_love"))
        self.assertRedirects(response, reverse("show_main"))

    def test_landing_uses_placeholders_and_shared_wanted_posts(self):
        user = get_user_model().objects.create_user(username="student")
        post = WantedPost.objects.create(requester=user, title="Looking for a desk lamp", budget=60000)
        response = self.client.get(reverse("show_main"))
        self.assertContains(response, "Item photo placeholder", count=12)
        self.assertContains(response, 'data-hanging-carousel')
        self.assertContains(response, 'data-carousel-next')
        self.assertContains(response, '#books-sticker')
        self.assertContains(response, '#plant-sticker')
        self.assertEqual(response.context["wanted_cards"][0]["title"], post.title)
        self.assertEqual(len(response.context["wanted_cards"]), 4)
        self.assertContains(response, "Pin yours here")
        self.assertContains(response, "Pin a Wanted")
        self.assertContains(response, "Three steps, Zero waste")
        self.assertNotContains(response, 'class="landing-discover"')
        self.assertNotContains(response, 'class="landing-discover landing-wanted"')

    def test_navbar_search_finds_items_and_wanted_posts(self):
        user = get_user_model().objects.create_user(username="student")
        item = Item.objects.create(owner=user, title="Desk lamp for sale", description="A working lamp",
                                   category="home", condition="good", listing_type="sale", price=25000,
                                   location="UI", source="user")
        post = WantedPost.objects.create(requester=user, title="Need a desk lamp", budget=60000)
        response = self.client.get(reverse("search_catalogue"), {"q": "desk lamp"})
        self.assertContains(response, item.title)
        self.assertContains(response, post.title)
        self.assertContains(response, item.get_absolute_url())
        self.assertContains(response, reverse("wanted_board:wanted_detail", args=[post.pk]))
        self.assertEqual(response.context["navbar_query"], "desk lamp")
        self.assertRedirects(self.client.get(reverse("search_catalogue"), {"q": "  "}), reverse("items:explore_items"))

    def test_ajax_search_empty_items_offers_prefilled_wanted_form(self):
        response = self.client.get(reverse("search_catalogue"), {"q": "Unlisted telescope"},
                                   HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        html = response.json()["html"]
        self.assertIn("No items found", html)
        self.assertIn("Pin What You Wanted", html)
        self.assertIn("create%3D1", html)
        self.assertIn("title%3DUnlisted%2Btelescope", html)
        self.assertIn(reverse("login"), html)
        user = get_user_model().objects.create_user(username="searcher")
        self.client.force_login(user)
        board = self.client.get(reverse("wanted_board:show_wanted"), {"create": "1", "title": "Unlisted telescope"})
        self.assertTrue(board.context["open_create_modal"])
        self.assertEqual(board.context["creation_form"].initial["title"], "Unlisted telescope")

    def test_ajax_search_without_query_does_not_return_catalogue_previews(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("search_catalogue"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"html": ""})

    def test_ajax_search_groups_items_and_wanted_and_escapes_query(self):
        user = get_user_model().objects.create_user(username="poster")
        Item.objects.create(owner=user, title="Telescope for sale", category="other", condition="good",
                            listing_type="sale", price=25000, location="UI", source="user")
        WantedPost.objects.create(requester=user, title="Wanted telescope", budget=60000)
        response = self.client.get(reverse("search_catalogue"), {"q": "telescope"},
                                   HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        html = response.json()["html"]
        self.assertIn("Telescope for sale", html)
        self.assertIn("Wanted telescope", html)
        self.assertNotIn("No items found", html)
        response = self.client.get(reverse("search_catalogue"), {"q": '<script>alert(1)</script>'},
                                   HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertNotIn("<script>", response.json()["html"])


class GlobalSearchResultsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="search-owner")
        for number in range(17):
            Item.objects.create(owner=cls.user, title=f"Quasar item {number}", category="books",
                                condition="good", listing_type="sale", price=60000, location="Kukusan")
        Item.objects.create(owner=cls.user, title="Quasar sold", category="books", condition="good",
                            listing_type="sale", price=60000, location="UI", status="sold")
        for number in range(7):
            WantedPost.objects.create(requester=cls.user, title=f"Quasar wanted {number}", budget=180000, location="UI")

    def search(self, **params):
        return self.client.get(reverse("search_catalogue"), {"q": "Quasar", **params})

    def test_all_tab_counts_all_matches_but_previews_only_four_each(self):
        response = self.search()
        self.assertEqual(response.context["item_count"], 17)
        self.assertEqual(response.context["wanted_count"], 7)
        self.assertEqual(len(response.context["items"]), 4)
        self.assertEqual(len(response.context["search_wanted"]), 4)
        self.assertContains(response, 'class="explore-card"', count=4)
        self.assertTemplateUsed(response, "items/_card.html")
        self.assertContains(response, 'class="wanted-card"', count=4)
        self.assertContains(response, "See all 17 items")
        self.assertContains(response, "See all 7 wanted posts")
        self.assertContains(response, "WELL USED")
        self.assertNotContains(response, "Quasar sold")
        self.assertNotContains(response, "Pin yours here")

    def test_items_tab_pages_only_available_items_and_preserves_query(self):
        response = self.search(type="items", page="2")
        self.assertEqual(len(response.context["items"]), 5)
        self.assertEqual(response.context["search_wanted"], [])
        self.assertNotContains(response, 'id="search-wanted-title"')
        self.assertContains(response, "Page 2 of 2")
        self.assertIn("q=Quasar&type=items&page=1", response.context["previous_url"])
        self.assertEqual(response.context["selected_type"], "items")

    def test_wanted_tab_keeps_request_notes_and_offer_actions(self):
        response = self.search(type="wanted")
        self.assertEqual(response.context["items"], [])
        self.assertEqual(len(response.context["search_wanted"]), 7)
        self.assertNotContains(response, 'class="explore-card"')
        self.assertContains(response, "data-open-item-offer-modal", count=7)
        self.assertContains(response, 'id="item-offer-modal"')
        self.client.force_login(self.user)
        response = self.search(type="wanted")
        self.assertContains(response, "Manage post", count=7)

    def test_empty_states_are_specific_to_the_selected_tab(self):
        for result_type, message in (("all", "No matches for"), ("items", "No available items found."),
                                     ("wanted", "No wanted posts found.")):
            response = self.client.get(reverse("search_catalogue"), {"q": "NoSuchQuasarResult", "type": result_type})
            self.assertContains(response, message)
            self.assertContains(response, "Pin What You Wanted")
        response = self.client.get(reverse("search_catalogue"), {"q": "wanted 6"})
        self.assertContains(response, "No available items found.")
        self.assertContains(response, "Quasar wanted 6")

    def test_free_items_show_free_and_invalid_tab_falls_back_to_all(self):
        Item.objects.create(owner=self.user, title="Quasar free", category="books", condition="good",
                            listing_type="free", price=0, location="UI")
        response = self.search(type="invalid")
        self.assertEqual(response.context["selected_type"], "all")
        self.assertContains(response, '>FREE</p>')
        self.assertNotContains(response, '>Rp0</p>')

    def test_explore_and_global_search_use_the_same_card_and_uploaded_photo(self):
        item = Item.objects.create(owner=self.user, title="Shared card photo", category="books", condition="good",
                                   listing_type="sale", price=20000, location="UI", image="item_photos/shared-card.png")
        for route in ("search_catalogue", "items:explore_items"):
            response = self.client.get(reverse(route), {"q": "Shared card photo"})
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "items/_card.html")
            self.assertTemplateUsed(response, "items/_item_image.html")
            self.assertContains(response, item.image.url)

    def test_navbar_ajax_still_previews_both_catalogues_from_any_tab(self):
        response = self.client.get(reverse("search_catalogue"), {"q": "Quasar", "type": "items"},
                                   HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn("Quasar wanted", response.json()["html"])
        self.assertIn("Quasar item", response.json()["html"])

    def test_invalid_pages_do_not_crash_and_counts_stay_correct(self):
        for raw_page in ("abc", "-1", "9999999999999999999999"):
            response = self.search(type="items", page=raw_page)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["item_count"], 17)
            self.assertIn(response.context["page_obj"].number, (1, 2))

    def test_query_html_is_escaped_and_special_characters_survive_tab_urls(self):
        from urllib.parse import parse_qs, urlsplit
        query = '<script>alert("x")</script> & 50%'
        response = self.client.get(reverse("search_catalogue"), {"q": query})
        self.assertNotContains(response, '<script>alert("x")</script>')
        for key in ("all_url", "items_url", "wanted_url"):
            self.assertEqual(parse_qs(urlsplit(response.context[key]).query)["q"], [query])
