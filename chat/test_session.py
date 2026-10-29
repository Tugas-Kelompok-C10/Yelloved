import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Message


class ChatSessionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="session-alice")
        self.bob = User.objects.create_user(username="session-bob")
        self.peer = User.objects.create_user(username="session-peer")
        self.client.force_login(self.alice)
        self.url = reverse("chat:messages", args=[self.peer.pk])

    def test_old_tab_cannot_send_under_new_account(self):
        identity = self.client.get(self.url)["X-Chat-Session"]
        self.client.force_login(self.bob)
        response = self.client.post(self.url, {"body": "Old account draft", "client_id": uuid.uuid4()}, HTTP_X_CHAT_SESSION=identity)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "chat_session_changed")
        self.assertFalse(Message.objects.exists())
        self.assertEqual(self.client.get(self.url, HTTP_X_CHAT_SESSION=identity).status_code, 409)

    def test_expired_and_rotated_session_are_detected(self):
        identity = self.client.get(self.url)["X-Chat-Session"]
        self.client.logout()
        self.assertEqual(self.client.get(self.url, HTTP_X_CHAT_SESSION=identity).status_code, 401)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url, HTTP_X_CHAT_SESSION=identity).status_code, 409)

    def test_current_session_can_send_and_responses_are_not_cached(self):
        identity = self.client.get(self.url)["X-Chat-Session"]
        response = self.client.post(self.url, {"body": "Hello", "client_id": uuid.uuid4()}, HTTP_X_CHAT_SESSION=identity)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Cache-Control"], "private, no-store")
