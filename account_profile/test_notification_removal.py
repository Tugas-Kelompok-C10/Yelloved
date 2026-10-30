from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class NotificationRemovalTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='without-notification-bell')
        self.client.force_login(user)

    def test_navbar_removes_bell_but_keeps_chat_and_activity(self):
        response = self.client.get(reverse('account_profile:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="notification-popover"')
        self.assertNotContains(response, '/account/notifications/')
        self.assertContains(response, 'data-chat-notifications')
        self.assertContains(response, 'matching-popover')
        self.assertNotIn('matching_notifications', response.context)

    def test_removed_settings_and_api_are_not_accessible(self):
        self.assertEqual(self.client.get('/account/notifications/').status_code, 404)
        self.assertEqual(self.client.get('/account/api/notifications/').status_code, 404)
        self.assertEqual(self.client.patch('/account/api/notifications/', '{}', content_type='application/json').status_code, 404)

    def test_activity_preview_still_returns_its_summary(self):
        response = self.client.get(reverse('item_matching:activity_preview'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('html', response.json())
        self.assertEqual(response.json()['pending'], 0)
