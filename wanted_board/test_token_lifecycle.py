from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .creation import issue_creation_token
from .models import WantedCreationReceipt, WantedPost


class WantedTokenLifecycleTests(TestCase):
    def test_deleted_post_cannot_be_recreated_using_old_form(self):
        user = get_user_model().objects.create_user(username="token-owner")
        self.client.force_login(user)
        payload = {"title": "Lamp", "description": "Study lamp", "category": "home", "budget": 10000,
                   "creation_token": issue_creation_token(user)}
        url = reverse("wanted_board:create_wanted")
        ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        first = self.client.post(url, payload, **ajax)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.client.post(url, payload, **ajax).json()["uid"], first.json()["uid"])
        WantedPost.objects.filter(pk=first.json()["uid"]).delete()
        self.assertIsNotNone(WantedCreationReceipt.objects.get(pk=first.json()["uid"]).deleted_at)
        response = self.client.post(url, payload, **ajax)
        self.assertEqual(response.status_code, 422)
        self.assertIn("already used", response.json()["errors"]["__all__"][0]["message"])
        self.assertFalse(WantedPost.objects.exists())

    def test_user_cascade_deletion_does_not_leave_orphan_receipts(self):
        user = get_user_model().objects.create_user(username="cascade-owner")
        WantedPost.objects.create(requester=user, title="Lamp", budget=10000)
        user.delete()
        self.assertFalse(WantedCreationReceipt.objects.exists())
