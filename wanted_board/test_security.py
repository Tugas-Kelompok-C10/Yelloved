from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from .models import WantedPost


@patch('wanted_board.views.get_sample_wanted_posts', return_value=())
class WantedSecurityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='security-owner')
        self.payload = '<img src=x onerror=alert(1)>'
        self.post = WantedPost.objects.create(
            requester=self.owner, title=self.payload, description=self.payload,
            location=self.payload, category='other', budget=10000,
        )
        self.client.force_login(self.owner)

    def test_detail_and_ajax_cards_escape_user_text(self, _):
        detail = self.client.get(reverse('wanted_board:wanted_detail', args=[self.post.pk]))
        self.assertContains(detail, escape(self.payload))
        self.assertNotContains(detail, self.payload)
        result = self.client.get(reverse('wanted_board:show_wanted'),
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
        self.assertIn(str(escape(self.payload)), result['html'])
        self.assertNotIn(self.payload, result['html'])
        # Escape when rendering, not when saving: avoid double-encoded text.
        self.post.refresh_from_db()
        self.assertEqual(self.post.description, self.payload)

    def test_crud_rejects_missing_or_invalid_csrf_tokens(self, _):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        urls = [reverse('wanted_board:create_wanted')] + [
            reverse(f'wanted_board:{action}', args=[self.post.pk])
            for action in ('edit_wanted', 'delete_wanted', 'update_status', 'create_offer')
        ]
        for url in urls:
            for data in ({}, {'csrfmiddlewaretoken': 'invalid'}):
                with self.subTest(url=url, data=data):
                    self.assertEqual(protected.post(url, data).status_code, 403)
        self.assertTrue(WantedPost.objects.filter(pk=self.post.pk).exists())

    def test_ajax_edit_accepts_valid_csrf_and_escapes_its_html_response(self, _):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        protected.get(reverse('wanted_board:wanted_detail', args=[self.post.pk]))
        response = protected.post(reverse('wanted_board:edit_wanted', args=[self.post.pk]), {
            'csrfmiddlewaretoken': protected.cookies['csrftoken'].value,
            'revision': self.post.updated_at.isoformat(), 'title': self.payload,
            'description': self.payload, 'location': self.payload,
            'category': 'other', 'budget': '10000',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(escape(self.payload)), response.json()['detail_html'])
        self.assertNotIn(self.payload, response.json()['detail_html'])
