from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .creation import issue_creation_token
from .models import WantedPost

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class WantedAjaxCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ajax-owner")
        self.client.force_login(self.user)
        self.post = WantedPost.objects.create(requester=self.user, title="Lamp", description="Desk lamp", budget=10000)

    def test_create_returns_feedback_without_queuing_a_second_toast(self):
        response = self.client.post(reverse("wanted_board:create_wanted"), {
            "title": "Chair", "description": "Study chair", "category": "home", "budget": 50000,
            "creation_token": issue_creation_token(self.user),
        }, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertIn("created", response.json()["message"])
        self.assertEqual(response.json()["board_url"], reverse("wanted_board:show_wanted"))
        self.assertNotContains(self.client.get(response.json()["board_url"]), "Your wanted post has been created.")

    def test_edit_returns_persisted_detail_and_new_revision(self):
        response = self.client.post(reverse("wanted_board:edit_wanted", args=[self.post.pk]), {
            "title": "Updated lamp", "description": "Compact lamp", "category": "home", "budget": 20000,
            "revision": self.post.updated_at.isoformat(),
        }, **AJAX)
        self.post.refresh_from_db()
        data = response.json()
        self.assertEqual(data["revision"], self.post.updated_at.isoformat())
        self.assertIn("Updated lamp", data["detail_html"])
        self.assertIn("Compact lamp", data["detail_html"])

    def test_ajax_delete_returns_json_and_removes_only_owners_post(self):
        response = self.client.post(reverse("wanted_board:delete_wanted", args=[self.post.pk]), **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted", response.json()["message"])
        self.assertFalse(WantedPost.objects.filter(pk=self.post.pk).exists())

    def test_foreign_ajax_delete_is_rejected_and_post_remains(self):
        self.client.force_login(get_user_model().objects.create_user(username="ajax-other"))
        response = self.client.post(reverse("wanted_board:delete_wanted", args=[self.post.pk]), **AJAX)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WantedPost.objects.filter(pk=self.post.pk).exists())
