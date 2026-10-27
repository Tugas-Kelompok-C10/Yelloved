import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_price_offers(apps, schema_editor):
    offers = apps.get_model("wanted_board", "Offer")
    database = schema_editor.connection.alias
    for offer in offers.objects.using(database).select_related("wanted_post").iterator():
        offers.objects.using(database).filter(pk=offer.pk).update(
            wanted_post_uuid_id=offer.wanted_post.uid
        )
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0013_prepare_uuid_primary_key"),
        ("item_matching", "0002_wantedpost_uuid_relation"),
    ]

    operations = [
        migrations.AddField(
            model_name="offer", name="wanted_post_uuid",
            field=models.ForeignKey(to="wanted_board.wantedpostuuid", null=True,
                                    on_delete=django.db.models.deletion.CASCADE, related_name="+"),
        ),
        migrations.RunPython(move_price_offers),
        migrations.RemoveConstraint(model_name="offer", name="unique_offer_per_user_and_wanted_post"),
        migrations.RemoveField(model_name="offer", name="wanted_post"),
        migrations.RenameField(model_name="offer", old_name="wanted_post_uuid", new_name="wanted_post"),
        migrations.AlterField(
            model_name="offer", name="wanted_post",
            field=models.ForeignKey(to="wanted_board.wantedpostuuid", related_name="offers",
                                    on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.DeleteModel(name="WantedPost"),
        migrations.RenameModel(old_name="WantedPostUUID", new_name="WantedPost"),
        migrations.AlterField(
            model_name="wantedpost", name="requester",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name="wanted_posts",
                                    on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(model_name="wantedpost", name="created_at", field=models.DateTimeField(auto_now_add=True)),
        migrations.AlterField(model_name="wantedpost", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.AddConstraint(
            model_name="offer",
            constraint=models.UniqueConstraint(fields=["wanted_post", "offerer"], name="unique_offer_per_user_and_wanted_post"),
        ),
    ]
