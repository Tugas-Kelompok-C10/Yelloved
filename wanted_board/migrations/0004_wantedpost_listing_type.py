from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0003_wantedpost_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="wantedpost",
            name="listing_type",
            field=models.CharField(
                choices=[("sell", "Jual"), ("trade", "Trade")],
                default="sell",
                max_length=10,
            ),
        ),
    ]
