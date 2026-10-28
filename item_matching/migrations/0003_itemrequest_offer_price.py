import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("item_matching", "0002_wantedpost_uuid_relation"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemrequest",
            name="offer_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Nominal penawaran",
            ),
        ),
    ]
