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


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    order_updates = models.BooleanField(default=True)
    wanted_updates = models.BooleanField(default=True)
    account_updates = models.BooleanField(default=True)
    promotions = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferensi notifikasi {self.user.username}"
