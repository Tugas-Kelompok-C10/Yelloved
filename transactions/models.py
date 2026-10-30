from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Transaction(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    TRANSACTION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    order_id = models.CharField(max_length=100, unique=True)

    PAYMENT_METHOD_CHOICES = [
        ("cod", "COD"),
        ("qris", "QRIS"),
        ("va", "Virtual Account"),
    ]

    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default="cod",
    )

    cod_meeting_location = models.CharField(
        max_length=255,
        blank=True,
    )

    cod_meeting_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    

    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    shipping_address = models.TextField()

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )

    transaction_status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default="pending"
    )

    midtrans_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    # Informasi pembayaran dari Midtrans
    midtrans_qr_code_url = models.URLField(
        max_length=500,
        blank=True,
    )

    virtual_account_bank = models.CharField(
        max_length=20,
        blank=True,
    )

    virtual_account_number = models.CharField(
        max_length=100,
        blank=True,
    )

    virtual_account_bill_key = models.CharField(
        max_length=100,
        blank=True,
    )

    virtual_account_biller_code = models.CharField(
        max_length=50,
        blank=True,
    )

    midtrans_expiry_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_id



class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.CASCADE,
        related_name="cart_entries",
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"],
                name="unique_user_cart_item",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.item.title} ({self.quantity})"


class TransactionItem(models.Model):
    """Purchase provenance for reviews; seller is captured when the order is created."""
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='review_items')
    item = models.ForeignKey('items.Item', null=True, on_delete=models.SET_NULL)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name='reviewable_sales')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['transaction', 'item'], name='unique_review_purchase_item')]
