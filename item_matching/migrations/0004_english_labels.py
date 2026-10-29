import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Only labels change (status choices and verbose names); no database columns are touched."""

    dependencies = [
        ("items", "0004_alter_item_image_url"),
        ("item_matching", "0003_itemrequest_offer_price"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemoffer",
            name="message",
            field=models.TextField(blank=True, max_length=1000, verbose_name="Message"),
        ),
        migrations.AlterField(
            model_name="itemoffer",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")],
                default="pending", max_length=10),
        ),
        migrations.AlterField(
            model_name="itemrequest",
            name="message",
            field=models.TextField(blank=True, max_length=1000, verbose_name="Message"),
        ),
        migrations.AlterField(
            model_name="itemrequest",
            name="offer_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Offer amount"),
        ),
        migrations.AlterField(
            model_name="itemrequest",
            name="offered_item",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="swap_offers", to="items.item", verbose_name="Item to swap"),
        ),
        migrations.AlterField(
            model_name="itemrequest",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("cancelled", "Cancelled")],
                default="pending", max_length=10),
        ),
    ]
