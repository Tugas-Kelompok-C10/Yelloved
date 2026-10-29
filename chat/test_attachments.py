import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Message


class ChatAttachmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sender = User.objects.create_user(username="file-sender")
        self.receiver = User.objects.create_user(username="file-receiver")
        self.other = User.objects.create_user(username="file-outsider")
        self.client.force_login(self.sender)
        self.url = reverse("chat:messages", args=[self.receiver.pk])
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        storage = patch.object(Message._meta.get_field("attachment"), "storage", FileSystemStorage(location=directory.name))
        storage.start()
        self.addCleanup(storage.stop)

    def send(self, filename="note.txt", content=b"Hello", **changes):
        payload = {"client_id": uuid.uuid4(), "body": "", "attachment": SimpleUploadedFile(filename, content)}
        payload.update(changes)
        return self.client.post(self.url, payload)

    def test_file_only_message_and_private_download(self):
        response = self.send()
        self.assertEqual(response.status_code, 201)
        url = response.json()["entry"]["attachment"]["url"]
        self.client.force_login(self.receiver)
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"Hello")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_oversized_and_disguised_files_are_rejected(self):
        for filename, content in [("attack.html", b"<script>"), ("photo.png", b"not an image"),
                                  ("fake.pdf", b"not a PDF"), ("huge.txt", b"x" * (5 * 1024 * 1024 + 1))]:
            with self.subTest(filename=filename):
                self.assertEqual(self.send(filename, content).status_code, 422)
        self.assertFalse(Message.objects.exists())

    def test_deleted_or_missing_file_is_not_downloadable(self):
        url = self.send().json()["entry"]["attachment"]["url"]
        message = Message.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("chat:message_action", args=[message.pk, "delete"]), {"revision": message.edited_at.isoformat()})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(message.attachment.storage.exists(message.attachment.name))

    def test_retry_does_not_create_duplicate_attachments(self):
        token = uuid.uuid4()
        self.assertEqual(self.send(client_id=token).status_code, 201)
        self.assertEqual(self.send(client_id=token).status_code, 200)
        self.assertEqual(Message.objects.count(), 1)

    def test_storage_failure_does_not_send_text_without_attachment(self):
        with patch.object(Message._meta.get_field("attachment").storage, "save", side_effect=OSError("Disk unavailable")):
            self.assertEqual(self.send(body="Hello").status_code, 503)
        self.assertFalse(Message.objects.exists())
