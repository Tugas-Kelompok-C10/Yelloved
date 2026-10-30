from django.db import models
from django.conf import settings

class Profile(models.Model):
    GENDER_CHOICES = [
        ("female", "Perempuan"),
        ("male", "Laki-laki"),
        ("other", "Lainnya"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile")
    photo = models.FileField(blank=True, upload_to="profile_photos/")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Tanggal lahir")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, verbose_name="Jenis kelamin")
    phone_number = models.CharField(max_length=30, blank=True, verbose_name="Nomor HP")

    def __str__(self):
        return f"Profil {self.user.username}"


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_addresses")
    label = models.CharField(max_length=40, default="Rumah")
    recipient_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=12, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_default", "label", "recipient_name")

    def __str__(self):
        return f"{self.label} — {self.recipient_name}"


class PaymentMethod(models.Model):
    METHOD_CHOICES = [
        ("bank", "Transfer bank"),
        ("e_wallet", "E-wallet"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_payment_methods")
    method_type = models.CharField(max_length=12, choices=METHOD_CHOICES)
    provider = models.CharField(max_length=60, verbose_name="Nama bank / e-wallet")
    account_name = models.CharField(max_length=150, verbose_name="Nama pemilik")
    account_identifier = models.CharField(max_length=80, verbose_name="Nomor rekening / HP")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_default", "method_type", "provider")

    def __str__(self):
        return f"{self.provider} — {self.account_name}"

    @property
    def masked_identifier(self):
        return f"•••• {self.account_identifier[-4:]}"




class Review(models.Model):
    transaction = models.OneToOneField('transactions.Transaction', on_delete=models.CASCADE, related_name='review')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='written_reviews')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5')]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.rating is None or not 1 <= self.rating <= 5:
            raise ValidationError({'rating': 'Choose a rating from 1 to 5.'})
        if not self.transaction_id or not self.reviewer_id or not self.seller_id:
            raise ValidationError('A completed purchase, buyer, and seller are required.')
        if self.transaction.buyer_id != self.reviewer_id:
            raise ValidationError('Only the buyer can review this order.')
        if self.transaction.transaction_status != 'completed':
            raise ValidationError('Reviews are available only after the order is completed.')
        if self.reviewer_id == self.seller_id:
            raise ValidationError('You cannot review yourself.')
        if not self.transaction.review_items.filter(seller_id=self.seller_id).exists():
            raise ValidationError('This seller is not part of your order.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)
