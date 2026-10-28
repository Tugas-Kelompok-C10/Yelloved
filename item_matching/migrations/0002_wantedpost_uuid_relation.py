import django.db.models.deletion
from django.db import migrations, models


def move_item_offers(apps, schema_editor):
    offers = apps.get_model("item_matching", "ItemOffer")
    database = schema_editor.connection.alias
    for offer in offers.objects.using(database).select_related("wanted_post").iterator():
        offers.objects.using(database).filter(pk=offer.pk).update(
            wanted_post_uuid_id=offer.wanted_post.uid
        )
    if schema_editor.connection.vendor == "postgresql":
        # Flush deferred FK trigger events before subsequent ALTER TABLE operations.
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):
    dependencies = [
        ("item_matching", "0001_initial"),
        ("wanted_board", "0013_prepare_uuid_primary_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemoffer", name="wanted_post_uuid",
            field=models.ForeignKey(to="wanted_board.wantedpostuuid", null=True,
                                    on_delete=django.db.models.deletion.CASCADE, related_name="+"),
        ),
        migrations.RunPython(move_item_offers),
        migrations.RemoveConstraint(model_name="itemoffer", name="unique_item_offer_per_wanted_post"),
        migrations.RemoveField(model_name="itemoffer", name="wanted_post"),
        migrations.RenameField(model_name="itemoffer", old_name="wanted_post_uuid", new_name="wanted_post"),
        migrations.AlterField(
            model_name="itemoffer", name="wanted_post",
            field=models.ForeignKey(to="wanted_board.wantedpostuuid", related_name="item_offers",
                                    on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddConstraint(
            model_name="itemoffer",
            constraint=models.UniqueConstraint(fields=["wanted_post", "item"], name="unique_item_offer_per_wanted_post"),
        ),
    ]
