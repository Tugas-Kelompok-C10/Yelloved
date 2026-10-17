from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date_of_birth", models.DateField(blank=True, null=True, verbose_name="Tanggal lahir")),
                ("gender", models.CharField(blank=True, choices=[("female", "Perempuan"), ("male", "Laki-laki"), ("other", "Lainnya")], max_length=10, verbose_name="Jenis kelamin")),
                ("phone_number", models.CharField(blank=True, max_length=30, verbose_name="Nomor HP")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="account_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
