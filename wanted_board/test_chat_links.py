from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import WantedPost
from .sample_data import SAMPLE_WANTED_POSTS


class WantedChatLinkTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="chat-poster")
        self.visitor = get_user_model().objects.create_user(username="chat-visitor")
        self.post = WantedPost.objects.create(requester=self.owner, title="Lamp", budget=10000)

    def test_detail_chat_and_poster_link_target_the_actual_owner(self):
        self.client.force_login(self.visitor)
        response = self.client.get(reverse("wanted_board:wanted_detail", args=[self.post.pk]))
        self.assertContains(response, f'data-offer-chat href="{reverse("chat:with_user", args=[self.owner.pk])}"')

    def test_board_modal_receives_each_cards_poster_chat_url(self):
        response = self.client.get(reverse("wanted_board:show_wanted"))
        self.assertContains(response, f'data-offer-chat="{reverse("chat:with_user", args=[self.owner.pk])}"')

    def test_owner_and_demo_posters_link_to_inbox(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("wanted_board:wanted_detail", args=[self.post.pk]))
        self.assertNotContains(response, f'href="{reverse("chat:with_user", args=[self.owner.pk])}"')
        demo = self.client.get(reverse("wanted_board:sample_wanted_detail", args=[SAMPLE_WANTED_POSTS[0]["slug"]]))
        self.assertContains(demo, f'data-offer-chat href="{reverse("chat:inbox")}"')
