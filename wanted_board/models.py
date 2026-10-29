from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class WantedPostQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {"id", "pk"} & kwargs.keys():
            raise ValidationError("A wanted post ID cannot be changed.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if {"id", "pk"} & set(fields):
            raise ValidationError("A wanted post ID cannot be changed.")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class WantedPost(models.Model):
    objects = WantedPostQuerySet.as_manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
    description = models.TextField(max_length=500)
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

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_pk = instance.pk
        return instance

    def save(self, *args, **kwargs):
        if not self.pk:
            raise ValidationError("A wanted post ID is required.")
        self.pk = uuid.UUID(str(self.pk))
        if getattr(self, "_original_pk", self.pk) != self.pk:
            raise ValidationError("A wanted post ID cannot be changed.")
        result = super().save(*args, **kwargs)
        self._original_pk = self.pk
        return result


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
