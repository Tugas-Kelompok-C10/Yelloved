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
