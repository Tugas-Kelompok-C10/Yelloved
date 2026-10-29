from django.contrib.auth import get_user_model
import uuid

from django.test import Client, TestCase
from django.urls import reverse

from .models import Conversation, Message


class ChatShellTests(TestCase):
    def test_chat_requires_login(self):
        self.assertEqual(self.client.get(reverse("chat:inbox")).status_code, 302)

    def test_chat_has_independent_layout_and_empty_state(self):
        self.client.force_login(get_user_model().objects.create_user(username="chat-owner"))
        response = self.client.get(reverse("chat:inbox"))
        self.assertContains(response, "No conversations yet.")
        self.assertNotContains(response, 'class="profile-sidebar"')

    def test_old_chat_link_redirects_to_chat_app(self):
        self.assertRedirects(self.client.get(reverse("transactions:pesan")), reverse("chat:inbox"), fetch_redirect_response=False)


class ChatMessageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice")
        self.bob = User.objects.create_user(username="bob")
        self.other = User.objects.create_user(username="outsider")
        self.client.force_login(self.alice)
        self.url = reverse("chat:messages", args=[self.bob.pk])

    def send(self, **changes):
        data = {"body": "Hello!", "client_id": str(uuid.uuid4())}
        data.update(changes)
        return self.client.post(self.url, data)

    def action(self, message, action, **changes):
        data = {"body": "Edited", "revision": message.edited_at.isoformat()}
        data.update(changes)
        return self.client.post(reverse("chat:message_action", args=[message.pk, action]), data)

    def test_opening_chat_does_not_create_empty_conversations(self):
        self.assertEqual(self.client.get(reverse("chat:with_user", args=[self.bob.pk])).status_code, 200)
        self.assertEqual(self.client.get(self.url).json()["messages"], [])
        self.assertFalse(Conversation.objects.exists())

    def test_messages_api_requires_authentication(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.send().status_code, 401)
        self.assertEqual(self.client.get(reverse("chat:inbox_data")).status_code, 401)

    def test_cannot_chat_with_self_missing_or_inactive_user(self):
        for peer in (self.alice.pk, 999999):
            self.assertEqual(self.client.get(reverse("chat:messages", args=[peer])).status_code, 404)
            self.assertEqual(self.client.get(reverse("chat:with_user", args=[peer])).status_code, 404)
        self.bob.is_active = False
        self.bob.save()
        self.assertEqual(self.send().status_code, 404)

    def test_send_retry_is_idempotent_and_does_not_overwrite(self):
        token = str(uuid.uuid4())
        self.assertEqual(self.send(client_id=token).status_code, 201)
        response = self.send(client_id=token, body="Retry must not overwrite")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.get().body, "Hello!")

    def test_both_directions_share_one_conversation(self):
        self.send()
        self.client.force_login(self.bob)
        response = self.client.post(reverse("chat:messages", args=[self.alice.pk]), {"body": "Hi Alice", "client_id": uuid.uuid4()})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Conversation.objects.count(), 1)
        entries = self.client.get(reverse("chat:messages", args=[self.alice.pk])).json()["messages"]
        self.assertEqual([row["mine"] for row in entries], [False, True])

    def test_unrelated_user_cannot_read_or_mutate_messages(self):
        self.send()
        message = Message.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("chat:messages", args=[self.alice.pk])).json()["messages"], [])
        for action in ("edit", "delete"):
            self.assertEqual(self.action(message, action).status_code, 404)
        threads = self.client.get(reverse("chat:inbox_data")).json()["conversations"]
        self.assertEqual(threads, [])

    def test_receiver_cannot_edit_or_delete_sender_message(self):
        self.send()
        message = Message.objects.get()
        self.client.force_login(self.bob)
        self.assertEqual(self.action(message, "delete").status_code, 404)
        self.assertEqual(self.action(message, "edit").status_code, 404)

    def test_validation_rejects_empty_long_or_invalid_token(self):
        for body in ("", "   ", "x" * 1001):
            self.assertEqual(self.send(body=body).status_code, 422)
        self.assertEqual(self.send(client_id="not-a-uuid").status_code, 422)
        self.assertFalse(Message.objects.exists())
        self.assertEqual(self.send(body="x" * 1000).status_code, 201)

    def test_edit_and_delete_use_revision_and_keep_deleted_message_empty(self):
        self.send()
        message = Message.objects.get()
        self.assertEqual(self.action(message, "edit").status_code, 200)
        self.assertEqual(self.action(message, "edit", body="Stale tab").status_code, 409)
        self.assertEqual(self.action(message, "delete").status_code, 409)
        message.refresh_from_db()
        self.assertEqual(message.body, "Edited")
        self.assertEqual(self.action(message, "delete").status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.body, "")
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(self.action(message, "edit").status_code, 409)
        self.assertTrue(self.client.get(self.url).json()["messages"][0]["deleted"])

    def test_wrong_or_missing_revision_does_not_change_messages(self):
        self.send()
        message = Message.objects.get()
        for revision in ("", "bad", "2026-99-99T00:00:00", "2026-01-01T00:00:00"):
            self.assertIn(self.action(message, "delete", revision=revision).status_code, (422, 409))
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

    def test_token_cannot_be_reused_for_another_recipient(self):
        token = uuid.uuid4()
        self.send(client_id=token)
        response = self.client.post(reverse("chat:messages", args=[self.other.pk]), {"body": "Wrong recipient", "client_id": token})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_history_is_bounded_and_older_pages_do_not_overlap(self):
        self.send()
        conversation = Conversation.objects.get()
        Message.objects.bulk_create([Message(conversation=conversation, sender=self.alice, body=str(i)) for i in range(55)])
        first = self.client.get(self.url).json()
        self.assertEqual(len(first["messages"]), 50)
        self.assertTrue(first["has_older"])
        second = self.client.get(self.url, {"before": first["messages"][0]["id"]}).json()
        self.assertEqual(len(second["messages"]), 6)
        self.assertFalse(second["has_older"])
        self.assertFalse({row["id"] for row in first["messages"]} & {row["id"] for row in second["messages"]})
        self.assertEqual(self.client.get(self.url, {"before": "invalid"}).status_code, 400)

    def test_csrf_is_required_for_send_and_edit(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.alice)
        self.assertEqual(protected.post(self.url, {"body": "Hi", "client_id": uuid.uuid4()}).status_code, 403)
        self.send()
        self.assertEqual(protected.post(reverse("chat:message_action", args=[Message.objects.get().pk, "delete"])).status_code, 403)
