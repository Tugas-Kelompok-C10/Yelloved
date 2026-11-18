from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import WantedPost


class WantedListApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-poster", email="private@example.com"
        )
        self.post = WantedPost.objects.create(
            requester=self.user, title="Study lamp", description="A small desk lamp",
            category=WantedPost.Category.HOME, budget=Decimal("150000.00"),
            location="UI Campus",
        )
        self.url = reverse("wanted_board:wanted_list_api")
        self.external_api = patch(
            "wanted_board.sample_data.requests.get",
            side_effect=AssertionError("Listing stored posts must not call an external API"),
        )
        self.external_api.start()
        self.addCleanup(self.external_api.stop)

    def test_anonymous_get_returns_public_database_fields_as_json(self):
        response = self.client.get(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), [{
            "id": str(self.post.pk), "title": self.post.title,
            "description": self.post.description, "category": self.post.category,
            "budget": "150000.00", "location": "UI Campus",
            "requester": self.user.pk, "requester_username": self.user.username,
            "status": "open", "created_at": response.data[0]["created_at"],
            "updated_at": response.data[0]["updated_at"],
        }])
        self.assertNotIn(self.user.email, response.content.decode())

    def test_browsable_api_renders_in_browser(self):
        response = self.client.get(self.url, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "rest_framework/api.html")
        self.assertContains(response, self.post.title)

    def test_only_open_posts_are_listed(self):
        for status in (WantedPost.Status.MATCHED, WantedPost.Status.FULFILLED, WantedPost.Status.CLOSED):
            WantedPost.objects.create(requester=self.user, title=status, budget=10000, status=status)
        response = self.client.get(self.url)
        self.assertEqual([row["id"] for row in response.json()], [str(self.post.pk)])

    def test_stored_demo_posts_are_included_newest_first(self):
        WantedPost.objects.filter(pk=self.post.pk).update(created_at=timezone.now() - timedelta(days=1))
        demo_user = get_user_model().objects.create_user(username="yelloved_wanted_demo")
        demo = WantedPost.objects.create(requester=demo_user, title="Stored demo", budget=20000)
        response = self.client.get(self.url)
        self.assertEqual([row["id"] for row in response.json()], [str(demo.pk), str(self.post.pk)])

    def test_empty_database_returns_empty_list(self):
        self.post.delete()
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_write_methods_are_not_allowed(self):
        self.client.force_login(self.user)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(self.url, {}, format="json")
            self.assertEqual(response.status_code, 405)
        self.assertEqual(WantedPost.objects.count(), 1)

    def test_existing_web_html_htmx_and_ajax_responses_are_preserved(self):
        url = reverse("wanted_board:show_wanted")
        html = self.client.get(url)
        self.assertEqual(html.status_code, 200)
        self.assertTemplateUsed(html, "wanted_post.html")
        self.assertContains(html, self.post.title)
        fragment = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(fragment.status_code, 200)
        self.assertTemplateUsed(fragment, "wanted_board/_results.html")
        ajax = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(ajax.status_code, 200)
        self.assertIn("html", ajax.json())
