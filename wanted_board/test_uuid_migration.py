import copy
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import TestCase

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone


class MigrationTestRouter:
    # Older data migrations do not explicitly call .using(schema_editor.alias).
    # Route those historical model queries into this test's isolated database.
    def db_for_read(self, model, **hints):
        return "wanted_uuid_migration_test"

    db_for_write = db_for_read


class UUIDPrimaryKeyMigrationTests(TestCase):
    def test_existing_posts_and_both_offer_relations_survive_uuid_conversion(self):
        """Exercise the upgrade with populated legacy tables in an isolated database."""
        alias = "wanted_uuid_migration_test"
        with tempfile.TemporaryDirectory() as directory:
            database = copy.deepcopy(settings.DATABASES["default"])
            database.update(ENGINE="django.db.backends.sqlite3", NAME=str(Path(directory) / "migration.sqlite3"), OPTIONS={})
            connections.databases[alias] = database
            connection = connections[alias]
            routing = override_settings(DATABASE_ROUTERS=[MigrationTestRouter()])
            routing.enable()
            try:
                before = [("wanted_board", "0012_wantedpost_uid"), ("item_matching", "0001_initial")]
                executor = MigrationExecutor(connection)
                executor.migrate(before)
                old_apps = executor.loader.project_state(before).apps
                user_model = old_apps.get_model(settings.AUTH_USER_MODEL)
                requester = user_model.objects.using(alias).create(username="requester")
                offerer = user_model.objects.using(alias).create(username="offerer")
                posts = old_apps.get_model("wanted_board", "WantedPost")
                first_uid, second_uid = uuid.uuid4(), uuid.uuid4()
                first = posts.objects.using(alias).create(
                    id=101, uid=first_uid, requester_id=requester.pk,
                    title="Legacy lamp", description="Original details", budget="120000",
                    category="home", image="wanted_references/original.png", location="UI",
                )
                second = posts.objects.using(alias).create(
                    id=102, uid=second_uid, requester_id=requester.pk,
                    title="Closed request", description="Closed", status="closed",
                )
                original_date = timezone.now() - timedelta(days=30)
                posts.objects.using(alias).filter(pk=first.pk).update(created_at=original_date, updated_at=original_date)
                price_offer = old_apps.get_model("wanted_board", "Offer").objects.using(alias).create(
                    wanted_post_id=first.pk, offerer_id=offerer.pk, message="Have one", offered_price="100000",
                )
                item = old_apps.get_model("items", "Item").objects.using(alias).create(
                    owner_id=offerer.pk, title="Lamp", category="home", condition="good",
                    listing_type="sale", price="100000", location="UI", image_url="https://example.com/lamp.png",
                )
                item_offer = old_apps.get_model("item_matching", "ItemOffer").objects.using(alias).create(
                    wanted_post_id=first.pk, item_id=item.pk, offerer_id=offerer.pk, message="An item offer",
                )

                after = [("wanted_board", "0014_uuid_primary_key"), ("item_matching", "0002_wantedpost_uuid_relation")]
                executor = MigrationExecutor(connection)
                executor.migrate(after)
                new_apps = executor.loader.project_state(after).apps
                new_posts = new_apps.get_model("wanted_board", "WantedPost")
                self.assertEqual(new_posts.objects.using(alias).count(), 2)
                self.assertEqual(new_posts._meta.pk.get_internal_type(), "UUIDField")
                self.assertNotIn("uid", {field.name for field in new_posts._meta.fields})
                migrated = new_posts.objects.using(alias).get(pk=first_uid)
                self.assertEqual(migrated.title, "Legacy lamp")
                self.assertEqual(migrated.description, "Original details")
                self.assertEqual(migrated.requester_id, requester.pk)
                self.assertEqual(migrated.image.name, "wanted_references/original.png")
                self.assertEqual(migrated.created_at, original_date)
                self.assertEqual(migrated.updated_at, original_date)
                self.assertEqual(new_posts.objects.using(alias).get(pk=second_uid).status, "closed")
                self.assertEqual(
                    new_apps.get_model("wanted_board", "Offer").objects.using(alias).get(pk=price_offer.pk).wanted_post_id,
                    first_uid,
                )
                self.assertEqual(
                    new_apps.get_model("item_matching", "ItemOffer").objects.using(alias).get(pk=item_offer.pk).wanted_post_id,
                    first_uid,
                )
                connection.check_constraints()
            finally:
                routing.disable()
                connection.close()
                del connections[alias]
                del connections.databases[alias]
