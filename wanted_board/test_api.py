from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .creation import issue_creation_token
from .models import WantedCreationEvent, WantedPost


class WantedListApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-poster", email="private@example.com"
        )
        self.post = WantedPost.objects.create(
            requester=self.user, title="Study lamp", description="A small desk lamp",
            category=WantedPost.Category.HOME, budget=Decimal("150000.00"),
            location="UI Campus",
        )
        self.url = reverse("wanted_board:wanted_list_api")
        self.external_api = patch(
            "wanted_board.sample_data.requests.get",
            side_effect=AssertionError("Listing stored posts must not call an external API"),
        )
        self.external_api.start()
        self.addCleanup(self.external_api.stop)

    def test_anonymous_get_returns_public_database_fields_as_json(self):
        response = self.client.get(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), [{
            "id": str(self.post.pk), "title": self.post.title,
            "description": self.post.description, "category": self.post.category,
            "budget": "150000.00", "location": "UI Campus",
            "requester": self.user.pk, "requester_username": self.user.username,
            "status": "open", "created_at": response.data[0]["created_at"],
            "updated_at": response.data[0]["updated_at"],
        }])
        self.assertNotIn(self.user.email, response.content.decode())

    def test_browsable_api_renders_in_browser(self):
        response = self.client.get(self.url, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "rest_framework/api.html")
        self.assertContains(response, self.post.title)

    def test_only_open_posts_are_listed(self):
        for status in (WantedPost.Status.MATCHED, WantedPost.Status.FULFILLED, WantedPost.Status.CLOSED):
            WantedPost.objects.create(requester=self.user, title=status, budget=10000, status=status)
        response = self.client.get(self.url)
        self.assertEqual([row["id"] for row in response.json()], [str(self.post.pk)])

    def test_stored_demo_posts_are_included_newest_first(self):
        WantedPost.objects.filter(pk=self.post.pk).update(created_at=timezone.now() - timedelta(days=1))
        demo_user = get_user_model().objects.create_user(username="yelloved_wanted_demo")
        demo = WantedPost.objects.create(requester=demo_user, title="Stored demo", budget=20000)
        response = self.client.get(self.url)
        self.assertEqual([row["id"] for row in response.json()], [str(demo.pk), str(self.post.pk)])

    def test_empty_database_returns_empty_list(self):
        self.post.delete()
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_collection_only_accepts_get_head_and_post(self):
        self.client.force_login(self.user)
        for method in ("put", "patch", "delete"):
            response = getattr(self.client, method)(self.url, {}, format="json")
            self.assertEqual(response.status_code, 405)
        self.assertEqual(WantedPost.objects.count(), 1)

    def detail_url(self, post=None):
        return reverse("wanted_board:wanted_detail_api", args=[(post or self.post).pk])

    def create_payload(self, **changes):
        payload = {
            "title": "Study chair", "description": "A chair for studying",
            "category": "home", "budget": "50000.00", "location": "Kukusan",
            "creation_token": issue_creation_token(self.user),
        }
        payload.update(changes)
        return payload

    def status_url(self):
        return reverse("wanted_board:wanted_status_api", args=[self.post.pk])

    def test_detail_and_missing_post(self):
        url = self.detail_url()
        self.assertEqual(self.client.get(url).json()["id"], str(self.post.pk))
        self.post.delete()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_search_category_sort_and_pagination(self):
        for number in range(13):
            WantedPost.objects.create(
                requester=self.user, title=f"Book {number}", description="For class",
                category="books", budget=number + 1,
            )
        response = self.client.get(self.url, {
            "search": "book", "category": "books", "sort": "budget_asc", "page": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 13)
        self.assertEqual(len(response.data["results"]), 12)
        self.assertEqual(response.data["results"][0]["title"], "Book 0")
        self.assertIn("search=book", response.data["next"])
        second = self.client.get(response.data["next"])
        self.assertEqual(len(second.data["results"]), 1)
        self.assertIsNone(second.data["next"])
        self.assertEqual(self.client.get(self.url, {"search": "nothing"}).json(), [])
        self.assertEqual(self.client.get(self.url, {"page": 999}).status_code, 404)
        for key in ("category", "sort", "mine"):
            self.assertEqual(self.client.get(self.url, {key: "invalid"}).status_code, 400)

    def test_my_posts_requires_login_and_includes_only_own_posts(self):
        self.assertEqual(self.client.get(self.url, {"mine": "true"}).status_code, 403)
        self.client.force_login(self.user)
        other = get_user_model().objects.create_user(username="other")
        WantedPost.objects.create(requester=other, title="Other post", budget=1)
        self.post.status = WantedPost.Status.CLOSED
        self.post.save()
        response = self.client.get(self.url, {"mine": "true", "status": "closed"})
        self.assertEqual([row["id"] for row in response.data], [str(self.post.pk)])
        self.assertEqual(self.client.get(self.url).json()[0]["title"], "Other post")

    def test_anonymous_users_cannot_write_or_get_create_options(self):
        self.assertEqual(self.client.post(self.url, self.create_payload(), format="json").status_code, 403)
        self.assertEqual(self.client.get(reverse("wanted_board:wanted_create_options_api")).status_code, 403)
        for method in ("put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)(self.detail_url(), {}, format="json").status_code, 403)
        self.assertEqual(self.client.post(self.status_url(), {}, format="json").status_code, 403)

    def test_owner_is_assigned_by_server_and_output_fields_are_not_writable(self):
        self.client.force_login(self.user)
        payload = self.create_payload(
            title="<b>Study chair</b>", requester=99999, status="matched",
            id="00000000-0000-0000-0000-000000000001",
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        post = WantedPost.objects.get(pk=response.data["id"])
        self.assertEqual(post.requester, self.user)
        self.assertEqual(post.status, WantedPost.Status.OPEN)
        self.assertEqual(post.title, "Study chair")
        self.assertNotEqual(str(post.pk), payload["id"])
        self.assertNotIn("creation_token", response.data)
        self.assertNotIn("revision", response.data)

    def test_validation_rejects_invalid_input_without_consuming_quota(self):
        self.client.force_login(self.user)
        for changes in (
            {"title": "<b></b>"}, {"title": "a" * 51}, {"description": " "},
            {"description": "a" * 501}, {"budget": "0"}, {"budget": "-1"},
            {"budget": None}, {"category": "invalid"}, {"creation_token": "invalid"},
        ):
            response = self.client.post(self.url, self.create_payload(**changes), format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(WantedPost.objects.count(), 1)
        self.assertEqual(WantedCreationEvent.objects.count(), 0)

    def test_tokens_are_required_user_bound_and_retries_do_not_duplicate(self):
        self.client.force_login(self.user)
        missing = self.create_payload()
        del missing["creation_token"]
        self.assertEqual(self.client.post(self.url, missing, format="json").status_code, 400)
        other = get_user_model().objects.create_user(username="token-owner")
        wrong_token = self.create_payload(creation_token=issue_creation_token(other))
        self.assertEqual(self.client.post(self.url, wrong_token, format="json").status_code, 400)
        payload = self.create_payload()
        first = self.client.post(self.url, payload, format="json")
        retry = self.client.post(self.url, payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["id"], retry.data["id"])
        self.assertEqual(WantedCreationEvent.objects.count(), 1)
        url = reverse("wanted_board:wanted_detail_api", args=[first.data["id"]])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 409)

    def test_creation_quota_is_shared_with_web_and_delete_does_not_reset_it(self):
        self.client.force_login(self.user)
        web = self.client.post(reverse("wanted_board:create_wanted"), self.create_payload(),
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(web.status_code, 200)
        payloads = [self.create_payload() for _ in range(4)]
        for payload in payloads:
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 201)
        self.assertEqual(self.client.post(self.url, payloads[0], format="json").status_code, 201)
        WantedPost.objects.filter(requester=self.user).delete()
        blocked = self.client.post(self.url, self.create_payload(), format="json")
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked["Retry-After"]), 0)

    def test_put_patch_and_stale_revision(self):
        self.client.force_login(self.user)
        detail = self.client.get(self.detail_url()).data
        payload = {"title": "New lamp", "revision": detail["updated_at"]}
        updated = self.client.patch(self.detail_url(), payload, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["description"], self.post.description)
        self.assertEqual(self.client.patch(self.detail_url(), payload, format="json").status_code, 409)
        self.assertEqual(self.client.patch(self.detail_url(), {"title": "No revision"}, format="json").status_code, 400)
        self.assertEqual(self.client.put(self.detail_url(), {
            "title": "Incomplete", "revision": updated.data["updated_at"],
        }, format="json").status_code, 400)
        full = {"title": "Full update", "description": "Compact lamp", "category": "home",
                "budget": "25000", "location": "Depok", "revision": updated.data["updated_at"]}
        self.assertEqual(self.client.put(self.detail_url(), full, format="json").status_code, 200)

    def test_other_user_cannot_update_delete_or_change_status(self):
        other = get_user_model().objects.create_user(username="not-owner")
        self.client.force_login(other)
        for method in ("put", "patch", "delete"):
            response = getattr(self.client, method)(self.detail_url(), {}, format="json")
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(self.status_url(), {}, format="json").status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Study lamp")

    def test_status_changes_and_matched_post_guards(self):
        self.client.force_login(self.user)
        closed = self.client.post(self.status_url(), {
            "status": "closed", "revision": self.post.updated_at.isoformat(),
        }, format="json")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.data["status"], "closed")
        self.assertEqual(self.client.patch(self.detail_url(), {
            "title": "Blocked", "revision": closed.data["updated_at"],
        }, format="json").status_code, 409)
        self.assertEqual(self.client.post(self.status_url(), {
            "status": "matched", "revision": closed.data["updated_at"],
        }, format="json").status_code, 409)
        self.post.status = WantedPost.Status.MATCHED
        self.post.save()
        self.assertEqual(self.client.delete(self.detail_url()).status_code, 409)
        self.assertEqual(self.client.post(self.status_url(), {
            "status": "open", "revision": self.post.updated_at.isoformat(),
        }, format="json").status_code, 409)

    def test_delete_is_empty_idempotent_and_missing_objects_are_404(self):
        self.client.force_login(self.user)
        deleted = self.client.delete(self.detail_url())
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")
        self.assertEqual(self.client.delete(self.detail_url()).status_code, 204)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 404)
        self.assertEqual(self.client.patch(self.detail_url(), {}, format="json").status_code, 404)

    def test_linked_transactions_prevent_delete_and_completed_status_changes(self):
        from item_matching.models import ItemOffer
        from transactions.models import Transaction

        self.client.force_login(self.user)
        seller = get_user_model().objects.create_user(username="seller")
        offer = ItemOffer.objects.create(wanted_post=self.post, offerer=seller, status="accepted")
        Transaction.objects.create(
            order_id="WANTED-API-TEST", buyer=self.user, seller=seller, accepted_offer=offer,
            item_name=self.post.title, total_amount=10000, shipping_address="",
            transaction_status="completed", payment_status="paid",
        )
        self.post.status = WantedPost.Status.FULFILLED
        self.post.save()
        self.assertEqual(self.client.delete(self.detail_url()).status_code, 409)
        self.assertEqual(self.client.post(self.status_url(), {
            "status": "open", "revision": self.post.updated_at.isoformat(),
        }, format="json").status_code, 409)
        self.assertTrue(WantedPost.objects.filter(pk=self.post.pk).exists())

    def test_real_session_requires_csrf_for_all_write_methods(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, self.create_payload(), format="json").status_code, 403)
        for method in ("put", "patch", "delete"):
            self.assertEqual(getattr(client, method)(self.detail_url(), {}, format="json").status_code, 403)
        self.assertEqual(client.post(self.status_url(), {}, format="json").status_code, 403)
        options = client.get(reverse("wanted_board:wanted_create_options_api"))
        self.assertEqual(options.status_code, 200)
        self.assertIn("csrftoken", client.cookies)
        self.assertEqual(len(options.data["categories"]), 7)
        payload = self.create_payload(creation_token=options.data["creation_token"])
        created = client.post(self.url, payload, format="json", HTTP_X_CSRFTOKEN=options.data["csrf_token"])
        self.assertEqual(created.status_code, 201)

    def test_existing_web_html_htmx_and_ajax_responses_are_preserved(self):
        url = reverse("wanted_board:show_wanted")
        html = self.client.get(url)
        self.assertEqual(html.status_code, 200)
        self.assertTemplateUsed(html, "wanted_post.html")
        self.assertContains(html, self.post.title)
        fragment = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(fragment.status_code, 200)
        self.assertTemplateUsed(fragment, "wanted_board/_results.html")
        ajax = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(ajax.status_code, 200)
        self.assertIn("html", ajax.json())
