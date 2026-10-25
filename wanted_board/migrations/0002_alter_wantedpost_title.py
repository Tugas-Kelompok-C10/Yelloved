from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wantedpost",
            name="title",
            field=models.CharField(max_length=25),
        ),
    ]
