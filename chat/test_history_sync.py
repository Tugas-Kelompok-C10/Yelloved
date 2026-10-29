import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Conversation, Message


class HistorySyncTests(TestCase):
    def setUp(self):
        # These tests build long histories quickly; send limits have their own tests.
        quota = patch('chat.rate_limits.MESSAGE_LIMIT', 1000)
        quota.start()
        self.addCleanup(quota.stop)
        self.owner = get_user_model().objects.create_user(username='sync-owner')
        self.peer = get_user_model().objects.create_user(username='sync-peer')
        self.client.force_login(self.owner)
        self.url = reverse('chat:messages', args=[self.peer.pk])

    def send(self, text='Hello', token=None):
        response = self.client.post(self.url, {'body': text, 'client_id': token or uuid.uuid4()})
        self.assertIn(response.status_code, (200, 201))
        return response.json()['entry']

    def test_catch_up_more_than_one_batch_and_retry_version_gaps(self):
        first = self.send()
        cursor = self.client.get(self.url).json()['sync_cursor']
        expected = [self.send(str(number))['id'] for number in range(105)]
        self.send(token=first['id'])  # A successful retry does not create another message.
        result = self.client.get(self.url, {'after': cursor}).json()
        self.assertEqual(len(result['messages']), 100)
        self.assertTrue(result['has_more_changes'])
        ids = [row['id'] for row in result['messages']]
        result = self.client.get(self.url, {'after': result['sync_cursor']}).json()
        ids += [row['id'] for row in result['messages']]
        self.assertEqual(ids, expected)
        self.assertFalse(result['has_more_changes'])
        self.assertEqual(self.client.get(self.url, {'after': result['sync_cursor']}).json()['messages'], [])

    def test_old_edits_and_deletions_are_delivered_after_latest_window(self):
        old = self.send('Old message')
        for number in range(51):
            self.send(str(number))
        initial = self.client.get(self.url).json()
        self.assertNotIn(old['id'], [row['id'] for row in initial['messages']])
        edit = self.client.post(reverse('chat:message_action', args=[old['id'], 'edit']),
                                {'body': 'Changed old message', 'revision': old['revision']}).json()['entry']
        delta = self.client.get(self.url, {'after': initial['sync_cursor']}).json()
        self.assertEqual(delta['messages'][0]['body'], 'Changed old message')
        self.assertEqual(delta['messages'][0]['created_version'], old['created_version'])
        self.client.post(reverse('chat:message_action', args=[old['id'], 'delete']), {'revision': edit['revision']})
        deleted = self.client.get(self.url, {'after': delta['sync_cursor']}).json()['messages']
        self.assertTrue(deleted[0]['deleted'])
        self.assertEqual(deleted[0]['body'], '')

    def test_resolve_lost_responses_is_scoped_to_conversation(self):
        old = self.send()
        other = get_user_model().objects.create_user(username='sync-other')
        other_url = reverse('chat:messages', args=[other.pk])
        self.assertEqual(self.client.get(other_url, {'resolve': old['id']}).json()['messages'], [])
        resolved = self.client.get(self.url, {'resolve': old['id']}).json()['messages']
        self.assertEqual(resolved[0]['id'], old['id'])
        for params in ({'after': '-1'}, {'after': 'invalid'}, {'after': '9999'}, {'resolve': 'invalid'}):
            self.assertEqual(self.client.get(self.url, params).status_code, 422)

    def test_inbox_pagination_and_account_bound_cursor(self):
        for number in range(52):
            peer = get_user_model().objects.create_user(username=f'inbox-peer-{number}')
            Conversation.objects.create(first_user=self.owner, second_user=peer)
        url = reverse('chat:inbox_data')
        first = self.client.get(url).json()
        second = self.client.get(url, {'cursor': first['next_cursor']}).json()
        self.assertEqual(len(first['conversations']), 50)
        self.assertEqual(len(second['conversations']), 2)
        ids = [row['peer_id'] for row in first['conversations'] + second['conversations']]
        self.assertEqual(len(set(ids)), 52)
        self.assertIsNone(second['next_cursor'])
        self.client.force_login(self.peer)
        self.assertEqual(self.client.get(url, {'cursor': first['next_cursor']}).status_code, 422)
        self.assertEqual(self.client.get(url, {'cursor': 'bad'}).status_code, 422)
