import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import wanted_board.validators


def copy_posts(apps, schema_editor):
    old_posts = apps.get_model("wanted_board", "WantedPost")
    new_posts = apps.get_model("wanted_board", "WantedPostUUID")
    database = schema_editor.connection.alias
    fields = (
        "requester_id", "title", "image", "description", "category", "budget",
        "location", "status", "created_at", "updated_at",
    )
    for row in old_posts.objects.using(database).values("uid", *fields).iterator():
        uid = row.pop("uid")
        new_posts.objects.using(database).create(id=uid, **row)


class Migration(migrations.Migration):
    dependencies = [("wanted_board", "0012_wantedpost_uid")]

    operations = [
        # A separate table avoids casting integers directly into UUIDs on PostgreSQL.
        # Neither stage removes uploaded images; historical models have no cleanup signals.
        migrations.CreateModel(
            name="WantedPostUUID",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("requester", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="+")),
                ("title", models.CharField(max_length=50)),
                ("image", models.ImageField(upload_to="wanted_references/", validators=[
                    django.core.validators.FileExtensionValidator(allowed_extensions=("jpg", "jpeg", "png", "webp")),
                    wanted_board.validators.validate_reference_image,
                ])),
                ("description", models.TextField()),
                ("category", models.CharField(max_length=20, default="other", choices=[
                    ("fashion", "Fashion"), ("books", "Books & Study"),
                    ("electronics", "Electronics"), ("home", "Home & Living"),
                    ("skincare", "Skincare"), ("kitchen_houseware", "Kitchen & Houseware"),
                    ("other", "Other"),
                ])),
                ("budget", models.DecimalField(max_digits=12, decimal_places=2, null=True, validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01"), message="Please enter a maximum budget greater than Rp0."),
                ])),
                ("location", models.CharField(max_length=120, blank=True)),
                ("status", models.CharField(max_length=12, default="open", choices=[
                    ("open", "Open"), ("fulfilled", "Fulfilled"), ("closed", "Closed"),
                ])),
                # Ordinary DateTimeFields preserve original timestamps during the copy.
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.RunPython(copy_posts),
    ]
