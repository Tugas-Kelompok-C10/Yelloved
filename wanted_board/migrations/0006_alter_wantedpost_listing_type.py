from django.db import migrations, models


def migrate_trade_to_free(apps, schema_editor):
    wanted_post = apps.get_model("wanted_board", "WantedPost")
    wanted_post.objects.filter(listing_type="trade").update(listing_type="free")


def restore_free_to_trade(apps, schema_editor):
    wanted_post = apps.get_model("wanted_board", "WantedPost")
    wanted_post.objects.filter(listing_type="free").update(listing_type="trade")


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0005_english_wanted_post_choices"),
    ]

    operations = [
        migrations.RunPython(migrate_trade_to_free, restore_free_to_trade),
        migrations.AlterField(
            model_name="wantedpost",
            name="listing_type",
            field=models.CharField(
                choices=[("sell", "Sell"), ("free", "Free")],
                default="sell",
                max_length=10,
            ),
        ),
    ]
