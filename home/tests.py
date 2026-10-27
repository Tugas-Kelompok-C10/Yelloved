from django.test import Client, TestCase
from django.urls import reverse


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
