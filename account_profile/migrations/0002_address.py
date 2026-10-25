from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("account_profile", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Address",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="Rumah", max_length=40)),
                ("recipient_name", models.CharField(max_length=150)),
                ("phone_number", models.CharField(max_length=30)),
                ("street_address", models.TextField()),
                ("city", models.CharField(max_length=100)),
                ("province", models.CharField(blank=True, max_length=100)),
                ("postal_code", models.CharField(blank=True, max_length=12)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_addresses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-is_default", "label", "recipient_name")},
        ),
    ]
