import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wanted_board", "0002_alter_wantedpost_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="wantedpost",
            name="image",
            field=models.FileField(
                default="",
                upload_to="wanted_references/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=("jpg", "jpeg", "png", "webp")
                    )
                ],
            ),
            preserve_default=False,
        ),
    ]
