"""Real concurrent database checks; use a file database or PostgreSQL."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from .models import WantedCreationEvent, WantedPost
from .rate_limits import CreationRateLimited, create_with_quota


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
