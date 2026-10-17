from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account_profile", "0002_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="photo",
            field=models.FileField(blank=True, upload_to="profile_photos/"),
        ),
    ]
