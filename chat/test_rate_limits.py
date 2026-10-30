import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Conversation, Message, MessageSendQuota
from .views import messages_api


class MessageRateTests(TestCase):
    def setUp(self):
        self.sender = get_user_model().objects.create_user(username='rate-sender')
        self.peer = get_user_model().objects.create_user(username='rate-peer')
        self.conversation = Conversation.objects.create(first_user=self.sender, second_user=self.peer)
        self.url = reverse('chat:messages', args=[self.peer.pk])
        self.client.force_login(self.sender)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        storage = patch.object(Message._meta.get_field('attachment'), 'storage', FileSystemStorage(location=folder.name))
        storage.start()
        self.addCleanup(storage.stop)

    def fill(self, count=30):
        Message.objects.bulk_create([Message(conversation=self.conversation, sender=self.sender, body='Hi') for _ in range(count)])

    def send(self, **changes):
        return self.client.post(self.url, {'body': 'Hello', 'client_id': uuid.uuid4(), **changes})

    def test_thirtieth_send_allowed_then_429_across_conversations(self):
        self.fill(29)
        self.assertEqual(self.send().status_code, 201)
        other = get_user_model().objects.create_user(username='rate-other-peer')
        self.url = reverse('chat:messages', args=[other.pk])
        response = self.send()
        self.assertEqual(response.status_code, 429)
        self.assertIn('30 messages in 1 minute', response.json()['message'])
        self.assertEqual(int(response['Retry-After']), response.json()['retry_after'])
        self.assertTrue(1 <= response.json()['retry_after'] <= 60)
        self.assertEqual(Message.objects.count(), 30)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_successful_retry_at_limit_and_deleted_message_do_not_resend(self):
        self.fill()
        message = Message.objects.first()
        Message.objects.filter(pk=message.pk).update(deleted_at=timezone.now(), body='')
        response = self.send(client_id=message.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['entry']['deleted'])
        self.assertEqual(self.send().status_code, 429)
        self.assertEqual(Message.objects.count(), 30)

    def test_expired_messages_and_other_accounts_have_separate_allowances(self):
        self.fill()
        self.client.force_login(self.peer)
        self.url = reverse('chat:messages', args=[self.sender.pk])
        self.assertEqual(self.send().status_code, 201)
        self.client.force_login(self.sender)
        self.url = reverse('chat:messages', args=[self.peer.pk])
        Message.objects.filter(sender=self.sender).update(created_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.send().status_code, 201)

    def test_invalid_input_and_failed_storage_do_not_consume_remaining_slot(self):
        self.fill(29)
        self.assertEqual(self.send(body='').status_code, 422)
        storage = Message._meta.get_field('attachment').storage
        with patch.object(storage, 'save', side_effect=OSError('Disk full')):
            self.assertEqual(self.send(attachment=SimpleUploadedFile('note.txt', b'Hello')).status_code, 503)
        self.assertEqual(Message.objects.count(), 29)
        self.assertEqual(self.send().status_code, 201)

    def test_over_limit_upload_never_writes_a_file(self):
        self.fill()
        storage = Message._meta.get_field('attachment').storage
        with patch.object(storage, 'save', wraps=storage.save) as save:
            response = self.send(attachment=SimpleUploadedFile('note.txt', b'Hello'))
            self.assertEqual(response.status_code, 429)
            save.assert_not_called()


class ConcurrentMessageRateTests(TransactionTestCase):
    def test_parallel_tabs_cannot_both_take_the_last_slot(self):
        database = str(connection.settings_dict['NAME'])
        if connection.vendor == 'sqlite' and (database == ':memory:' or 'mode=memory' in database):
            self.skipTest('Concurrent SQLite writes require a file-backed test database.')
        sender = get_user_model().objects.create_user(username='parallel-rate-sender')
        peers = [get_user_model().objects.create_user(username=f'parallel-rate-peer-{n}') for n in range(2)]
        conversation = Conversation.objects.create(first_user=sender, second_user=peers[0])
        Message.objects.bulk_create([Message(conversation=conversation, sender=sender, body='Hi') for _ in range(29)])
        MessageSendQuota.objects.create(user=sender)
        barrier = threading.Barrier(2)

        def send(peer):
            try:
                request = RequestFactory().post('/chat/', {'body': 'Final slot', 'client_id': uuid.uuid4()})
                request.user = sender
                request.session = SessionStore()
                barrier.wait(timeout=10)
                return messages_api(request, peer.pk).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(send, peers)), [201, 429])
        self.assertEqual(Message.objects.filter(sender=sender).count(), 30)
