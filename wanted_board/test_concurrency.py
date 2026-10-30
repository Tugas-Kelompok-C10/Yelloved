"""Real concurrent database checks; use a file database or PostgreSQL."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TransactionTestCase

from .models import Offer, WantedCreationEvent, WantedPost
from .rate_limits import CreationRateLimited, create_with_quota
from .views import create_offer, update_status


class WantedConcurrencyTests(TransactionTestCase):
    def setUp(self):
        database = str(connection.settings_dict["NAME"])
        if connection.vendor == "sqlite" and (database == ":memory:" or "mode=memory" in database):
            self.skipTest("Concurrent SQLite writes need a file-backed test database, not shared-cache memory.")
        self.user = get_user_model().objects.create_user(username="concurrent-owner")

    def test_concurrent_creates_cannot_exceed_five(self):
        defaults = {"title": "Lamp", "description": "Study lamp", "budget": 10000, "category": "home"}
        for _ in range(4):
            create_with_quota(self.user, uuid.uuid4(), defaults)
        barrier = threading.Barrier(3)

        def submit():
            try:
                barrier.wait(timeout=10)
                try:
                    create_with_quota(self.user, uuid.uuid4(), defaults)
                    return "created"
                except CreationRateLimited:
                    return "limited"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: submit(), range(3)))
        self.assertCountEqual(results, ["created", "limited", "limited"])
        self.assertEqual(WantedPost.objects.count(), 5)
        self.assertEqual(WantedCreationEvent.objects.count(), 5)

    def request_in_thread(self, view, user, pk, data):
        try:
            request = RequestFactory().post("/wanted-post/", data)
            request.user = user
            request.session = {}
            request._messages = FallbackStorage(request)
            response = view(request, pk)
            return response.status_code, [str(message) for message in request._messages]
        finally:
            connections.close_all()

    def test_closing_waits_until_offer_checked_and_saved(self):
        offerer = get_user_model().objects.create_user(username="concurrent-offerer")
        post = WantedPost.objects.create(requester=self.user, title="Lamp", budget=10000)
        entered, release = threading.Event(), threading.Event()
        original_insert = Offer.objects.get_or_create

        def paused_insert(*args, **kwargs):
            entered.set()  # The endpoint has already checked OPEN under the lock.
            if not release.wait(timeout=10):
                raise TimeoutError("Test did not release offer insertion")
            return original_insert(*args, **kwargs)

        with patch.object(Offer.objects, "get_or_create", paused_insert), ThreadPoolExecutor(max_workers=2) as pool:
            offer = pool.submit(self.request_in_thread, create_offer, offerer, post.pk, {"offered_price": 9000})
            try:
                self.assertTrue(entered.wait(timeout=5))
                closing = pool.submit(self.request_in_thread, update_status, self.user, post.pk, {"status": "closed"})
                with self.assertRaises(TimeoutError):
                    closing.result(timeout=0.2)
            finally:
                release.set()
            self.assertEqual(offer.result(timeout=5)[0], 302)
            self.assertEqual(closing.result(timeout=5)[0], 302)
        post.refresh_from_db()
        self.assertEqual(post.status, "closed")
        self.assertEqual(Offer.objects.count(), 1)  # Offer committed before closing.

    def test_offer_waits_for_closure_then_rejects_latest_status(self):
        offerer = get_user_model().objects.create_user(username="late-offerer")
        post = WantedPost.objects.create(requester=self.user, title="Lamp", budget=10000)
        entered, release = threading.Event(), threading.Event()
        original_save = WantedPost.save

        def paused_save(instance, *args, **kwargs):
            result = original_save(instance, *args, **kwargs)
            entered.set()  # Status updated, but its transaction has not committed.
            if not release.wait(timeout=10):
                raise TimeoutError("Test did not release status update")
            return result

        with patch.object(WantedPost, "save", paused_save), ThreadPoolExecutor(max_workers=2) as pool:
            closing = pool.submit(self.request_in_thread, update_status, self.user, post.pk, {"status": "fulfilled"})
            try:
                self.assertTrue(entered.wait(timeout=5))
                offer = pool.submit(self.request_in_thread, create_offer, offerer, post.pk, {"offered_price": 9000})
                with self.assertRaises(TimeoutError):
                    offer.result(timeout=0.2)
            finally:
                release.set()
            self.assertEqual(closing.result(timeout=5)[0], 302)
            status, messages = offer.result(timeout=5)
        self.assertEqual(status, 302)
        self.assertIn("This wanted post is no longer accepting offers.", messages)
        self.assertFalse(Offer.objects.exists())
