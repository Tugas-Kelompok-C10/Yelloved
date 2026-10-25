from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("account_profile", "0003_profile_photo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method_type", models.CharField(choices=[("bank", "Transfer bank"), ("e_wallet", "E-wallet")], max_length=12)),
                ("provider", models.CharField(max_length=60, verbose_name="Nama bank / e-wallet")),
                ("account_name", models.CharField(max_length=150, verbose_name="Nama pemilik")),
                ("account_identifier", models.CharField(max_length=80, verbose_name="Nomor rekening / HP")),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_payment_methods", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-is_default", "method_type", "provider")},
        ),
    ]
