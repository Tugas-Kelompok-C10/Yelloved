from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models

from .validators import validate_reference_image


class WantedPost(models.Model):
    class Category(models.TextChoices):
        FASHION = "fashion", "Fashion"
        BOOKS = "books", "Books & Study"
        ELECTRONICS = "electronics", "Electronics"
        HOME = "home", "Home & Living"
        SKINCARE = "skincare", "Skincare"
        KITCHEN_HOUSEWARE = "kitchen_houseware", "Kitchen & Houseware"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULFILLED = "fulfilled", "Fulfilled"
        CLOSED = "closed", "Closed"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wanted_posts",
    )
    title = models.CharField(max_length=50)
    image = models.ImageField(
        upload_to="wanted_references/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp")
            ),
            validate_reference_image,
        ],
    )
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=False,
        null=True,
        validators=[MinValueValidator(
            Decimal("0.01"),
            message="Please enter a maximum budget greater than Rp0.",
        )],
    )
    location = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Offer(models.Model):
    wanted_post = models.ForeignKey(
        WantedPost,
        on_delete=models.CASCADE,
        related_name="offers",
    )
    offerer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wanted_offers",
    )
    message = models.TextField()
    offered_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["wanted_post", "offerer"],
                name="unique_offer_per_user_and_wanted_post",
            )
        ]

    def __str__(self):
        return f"Offer from {self.offerer} for {self.wanted_post}"
