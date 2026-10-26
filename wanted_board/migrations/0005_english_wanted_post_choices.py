from django.db import migrations, models


def migrate_condition_values(apps, schema_editor):
    wanted_post = apps.get_model("wanted_board", "WantedPost")
    value_map = {
        "any": "well_used",
        "like_new": "lightly_used",
        "good": "well_used",
    }
    for old_value, new_value in value_map.items():
        wanted_post.objects.filter(preferred_condition=old_value).update(
            preferred_condition=new_value
        )


def restore_condition_values(apps, schema_editor):
    wanted_post = apps.get_model("wanted_board", "WantedPost")
    wanted_post.objects.filter(preferred_condition="lightly_used").update(
        preferred_condition="like_new"
    )
    wanted_post.objects.filter(preferred_condition="well_used").update(
        preferred_condition="good"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0004_wantedpost_listing_type"),
    ]

    operations = [
        migrations.RunPython(
            migrate_condition_values,
            restore_condition_values,
        ),
        migrations.AlterField(
            model_name="wantedpost",
            name="listing_type",
            field=models.CharField(
                choices=[("sell", "Sell"), ("trade", "Trade")],
                default="sell",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="wantedpost",
            name="preferred_condition",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("lightly_used", "Lightly used"),
                    ("well_used", "Well used"),
                ],
                default="lightly_used",
                max_length=20,
            ),
        ),
    ]
