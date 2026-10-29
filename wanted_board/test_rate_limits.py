from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .creation import issue_creation_token
from .models import WantedCreationEvent, WantedPost

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class WantedCreationRateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="quota-owner")
        self.client.force_login(self.user)
        self.url = reverse("wanted_board:create_wanted")

    def create(self, **changes):
        payload = {"title": "Lamp", "description": "Study lamp", "category": "home",
                   "budget": "10000", "creation_token": issue_creation_token(self.user)}
        payload.update(changes)
        return self.client.post(self.url, payload, **AJAX)

    def fill_quota(self):
        return [self.create() for _ in range(5)]

    def test_five_posts_allowed_sixth_returns_clear_429(self):
        self.assertTrue(all(response.status_code == 200 for response in self.fill_quota()))
        response = self.create()
        self.assertEqual(response.status_code, 429)
        self.assertIn("5 wanted posts in 10 minutes", response.json()["message"])
        self.assertIn("kept", response.json()["errors"]["__all__"][0]["message"])
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertLessEqual(response.json()["retry_after"], 600)
        self.assertEqual(WantedPost.objects.count(), 5)

    def test_retry_existing_token_at_limit_does_not_consume_quota(self):
        responses = self.fill_quota()
        # Reuse the signed token for an already-created UID.
        from django.core import signing
        token = signing.dumps({"uid": responses[0].json()["uid"], "user_id": self.user.pk}, salt="wanted_board.create")
        response = self.client.post(self.url, {"creation_token": token}, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WantedCreationEvent.objects.count(), 5)

    def test_invalid_form_does_not_consume_quota(self):
        self.assertEqual(self.create(budget="0").status_code, 422)
        self.assertEqual(WantedCreationEvent.objects.count(), 0)
        self.assertEqual(self.create().status_code, 200)

    def test_deleting_posts_does_not_reset_quota(self):
        self.fill_quota()
        WantedPost.objects.all().delete()
        self.assertEqual(self.create().status_code, 429)

    def test_window_expires_and_another_user_has_separate_quota(self):
        self.fill_quota()
        self.client.force_login(get_user_model().objects.create_user(username="quota-other"))
        other = self.client.session["_auth_user_id"]
        other_user = get_user_model().objects.get(pk=other)
        self.assertEqual(self.create(creation_token=issue_creation_token(other_user)).status_code, 200)
        self.client.force_login(self.user)
        WantedCreationEvent.objects.filter(quota__user=self.user).update(created_at=timezone.now() - timedelta(minutes=10))
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(WantedCreationEvent.objects.filter(quota__user=self.user).count(), 1)

    def test_regular_form_gets_rate_error_and_preserves_input(self):
        self.fill_quota()
        response = self.client.post(self.url, {"title": "Saved input", "description": "Keep this",
            "category": "home", "budget": "10000", "creation_token": issue_creation_token(self.user)})
        self.assertContains(response, "5 wanted posts in 10 minutes", status_code=429)
        self.assertContains(response, "Saved input", status_code=429)
