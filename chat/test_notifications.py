from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Conversation, Message


class ChatNotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.me = User.objects.create_user(username="reader")
        self.peer = User.objects.create_user(username="writer")
        self.outsider = User.objects.create_user(username="unrelated")
        self.thread = Conversation.objects.create(first_user=self.me, second_user=self.peer)
        self.client.force_login(self.me)

    def notification(self):
        return self.client.get(reverse("chat:notifications")).json()

    def test_count_only_incoming_unread_messages_and_acknowledge_only_delivered_ids(self):
        incoming = Message.objects.create(conversation=self.thread, sender=self.peer, body="Hi")
        Message.objects.create(conversation=self.thread, sender=self.me, body="My message")
        self.assertEqual(self.notification()["unread"], 1)
        # Merely fetching/preloading the conversation must not mark it read.
        self.client.get(reverse("chat:messages", args=[self.peer.pk]))
        self.assertEqual(self.notification()["unread"], 1)
        newer = Message.objects.create(conversation=self.thread, sender=self.peer, body="Arrived later")
        response = self.client.post(reverse("chat:mark_read", args=[self.peer.pk]), {"ids": [str(incoming.pk)]})
        self.assertEqual(response.json()["read"], 1)
        self.assertEqual(self.notification()["unread"], 1)
        newer.refresh_from_db()
        self.assertIsNone(newer.read_at)

    def test_other_user_cannot_mark_someone_elses_messages_read(self):
        incoming = Message.objects.create(conversation=self.thread, sender=self.peer, body="Private")
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("chat:mark_read", args=[self.peer.pk]), {"ids": [str(incoming.pk)]})
        self.assertEqual(response.json()["read"], 0)
        self.assertEqual(self.notification()["unread"], 0)

    def test_preview_contains_only_three_latest_conversations(self):
        for index in range(4):
            peer = get_user_model().objects.create_user(username=f"preview-{index}")
            thread = Conversation.objects.create(first_user=self.me, second_user=peer)
            Message.objects.create(conversation=thread, sender=peer, body=f"Message {index}")
        preview = self.notification()
        self.assertEqual(len(preview["conversations"]), 3)
        self.assertEqual(preview["conversations"][0]["preview"], "Message 3")
        self.assertEqual(preview["unread"], 4)

    def test_deleted_messages_do_not_count_and_unauthenticated_requests_are_rejected(self):
        from django.utils import timezone
        Message.objects.create(conversation=self.thread, sender=self.peer, body="", deleted_at=timezone.now())
        self.assertEqual(self.notification()["unread"], 0)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("chat:notifications")).status_code, 401)
