import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .creation import issue_creation_token
from .models import WantedPost
from .tests import reference_image


AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest", "HTTP_ACCEPT": "application/json"}


class WantedUploadWorkflowTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media_root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username="requester")
        self.other = get_user_model().objects.create_user(username="someone_else")
        self.client.force_login(self.user)
        self.token = issue_creation_token(self.user)
        self.create_url = reverse("wanted_board:create_wanted")

    def payload(self, **changes):
        data = {
            "title": "Study lamp", "description": "A compact desk lamp.",
            "category": "home", "budget": "150000", "location": "UI",
            "image": reference_image(), "creation_token": self.token,
        }
        data.update(changes)
        return data

    def create_post(self):
        response = self.client.post(self.create_url, self.payload(), **AJAX)
        self.assertEqual(response.status_code, 200, response.content)
        return WantedPost.objects.get(requester=self.user)

    def stored_files(self):
        return list(self.media_root.glob("wanted_references/*"))

    def test_create_form_issues_hidden_signed_token(self):
        response = self.client.get(reverse("wanted_board:show_wanted"))
        self.assertContains(response, 'name="creation_token"')
        self.assertTrue(response.context["creation_form"]["creation_token"].is_hidden)

    def test_repeat_submission_returns_same_post_and_stores_one_image(self):
        first = self.client.post(self.create_url, self.payload(), **AJAX)
        # A retry after a lost response need not upload the file again.
        second = self.client.post(self.create_url, {"creation_token": self.token}, **AJAX)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(WantedPost.objects.count(), 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_distinct_create_tokens_allow_posts_with_identical_titles(self):
        self.create_post()
        response = self.client.post(self.create_url, self.payload(
            creation_token=issue_creation_token(self.user)
        ), **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WantedPost.objects.count(), 2)
        self.assertEqual(len(set(WantedPost.objects.values_list("id", flat=True))), 2)

    def test_invalid_create_keeps_token_reusable_and_returns_field_errors(self):
        response = self.client.post(self.create_url, self.payload(budget="0"), **AJAX)
        self.assertEqual(response.status_code, 422)
        self.assertIn("budget", response.json()["errors"])
        self.assertFalse(WantedPost.objects.exists())
        self.assertEqual(self.stored_files(), [])
        self.create_post()

    def test_missing_forged_and_other_users_tokens_cannot_create(self):
        for token in ("", "forged", issue_creation_token(self.other)):
            with self.subTest(token=token):
                response = self.client.post(self.create_url, self.payload(creation_token=token), **AJAX)
                self.assertEqual(response.status_code, 422)
        self.assertFalse(WantedPost.objects.exists())

    def test_losing_create_race_does_not_overwrite_winner_or_store_image(self):
        post = self.create_post()
        original_image = post.image.name
        # Simulate another request committing after the initial existence check.
        with patch("wanted_board.views.WantedPost.objects.filter") as lookup:
            lookup.return_value.first.return_value = None
            response = self.client.post(self.create_url, self.payload(title="Retry"), **AJAX)
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.title, "Study lamp")
        self.assertEqual(post.image.name, original_image)
        self.assertEqual(len(self.stored_files()), 1)

    def test_uid_is_required_unique_and_immutable_via_save_and_queryset(self):
        post = self.create_post()
        uid = post.pk
        self.assertIsInstance(uid, uuid.UUID)
        self.assertEqual(WantedPost._meta.pk.name, "id")
        self.assertEqual(WantedPost._meta.pk.get_internal_type(), "UUIDField")
        self.assertNotIn("uid", {field.name for field in WantedPost._meta.fields})
        post.pk = uuid.uuid4()
        with self.assertRaises(ValidationError):
            post.save()
        with self.assertRaises(ValidationError):
            WantedPost.objects.filter(pk=uid).update(id=uuid.uuid4())
        with self.assertRaises(ValidationError):
            WantedPost.objects.bulk_update([post], ["id"])
        post.pk = uid
        post.refresh_from_db()
        self.assertEqual(post.pk, uid)
        post.pk = uuid.uuid4()
        with self.assertRaises(ValidationError):
            post.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            WantedPost.objects.create(requester=self.user, id=uid, title="Duplicate")
        with self.assertRaises(ValidationError):
            WantedPost(requester=self.user, id=None).save()

    def test_detail_url_uses_uuid_and_rejects_numeric_ids(self):
        post = self.create_post()
        url = reverse("wanted_board:wanted_detail", args=[post.pk])
        self.assertIn(str(post.pk), url)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/wanted-post/123/").status_code, 404)

    def test_ajax_edit_error_does_not_change_post_or_existing_photo(self):
        post = self.create_post()
        original_name = post.image.name
        response = self.client.post(reverse("wanted_board:edit_wanted", args=[post.pk]),
                                    self.payload(budget="0"), **AJAX)
        self.assertEqual(response.status_code, 422)
        self.assertIn("budget", response.json()["errors"])
        post.refresh_from_db()
        self.assertEqual(post.image.name, original_name)
        self.assertTrue((self.media_root / original_name).exists())
        self.assertEqual(len(self.stored_files()), 1)

    def test_ajax_edit_without_new_photo_preserves_photo_and_uid(self):
        post = self.create_post()
        original_name, original_uid = post.image.name, post.pk
        data = self.payload(title="Updated lamp", id=str(uuid.uuid4()))
        del data["image"]
        response = self.client.post(reverse("wanted_board:edit_wanted", args=[post.pk]), data, **AJAX)
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.title, "Updated lamp")
        self.assertEqual(post.pk, original_uid)
        self.assertEqual(post.image.name, original_name)

    def test_replaced_image_is_removed_only_after_commit(self):
        post = self.create_post()
        old_file = self.media_root / post.image.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("wanted_board:edit_wanted", args=[post.pk]),
                                        self.payload(image=reference_image("replacement.png")), **AJAX)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(old_file.exists())
        post.refresh_from_db()
        self.assertFalse(old_file.exists())
        self.assertTrue((self.media_root / post.image.name).exists())

    def test_delete_cleans_up_file_but_rollback_keeps_it(self):
        post = self.create_post()
        original_file = self.media_root / post.image.name
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    WantedPost.objects.filter(pk=post.pk).delete()
                    raise ValueError("Rollback")
            except ValueError:
                pass
        self.assertTrue(WantedPost.objects.filter(pk=post.pk).exists())
        self.assertTrue(original_file.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("wanted_board:delete_wanted", args=[post.pk]))
        self.assertFalse(original_file.exists())

    def test_shared_image_is_kept_until_last_post_is_deleted(self):
        post = self.create_post()
        shared = WantedPost.objects.create(requester=self.user, title="Shared", image=post.image.name)
        original_file = self.media_root / post.image.name
        with self.captureOnCommitCallbacks(execute=True):
            post.delete()
        self.assertTrue(original_file.exists())
        with self.captureOnCommitCallbacks(execute=True):
            shared.delete()
        self.assertFalse(original_file.exists())

    def test_other_user_cannot_edit_or_delete_by_ajax(self):
        post = self.create_post()
        self.client.force_login(self.other)
        for action in ("edit_wanted", "delete_wanted"):
            response = self.client.post(reverse(f"wanted_board:{action}", args=[post.pk]),
                                        self.payload(), **AJAX)
            self.assertEqual(response.status_code, 404)
        self.assertTrue(WantedPost.objects.filter(pk=post.pk).exists())
