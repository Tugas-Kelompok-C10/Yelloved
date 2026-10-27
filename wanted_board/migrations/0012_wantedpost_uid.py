import uuid

from django.db import migrations, models


def fill_existing_uids(apps, schema_editor):
    posts = apps.get_model("wanted_board", "WantedPost")
    database = schema_editor.connection.alias
    for pk in posts.objects.using(database).values_list("pk", flat=True).iterator():
        posts.objects.using(database).filter(pk=pk).update(uid=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("wanted_board", "0011_alter_wantedpost_budget")]

    operations = [
        migrations.AddField(
            model_name="wantedpost", name="uid",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_existing_uids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="wantedpost", name="uid",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
