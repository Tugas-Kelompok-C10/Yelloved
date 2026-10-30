from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account_profile", "0006_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="address",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="address",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
    ]
