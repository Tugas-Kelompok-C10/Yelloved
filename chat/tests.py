from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
