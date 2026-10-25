from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class WantedPost(models.Model):
    class Category(models.TextChoices):
        FASHION = "fashion", "Fashion"
        BOOKS = "books", "Books & Study"
        ELECTRONICS = "electronics", "Electronics"
        HOME = "home", "Home & Living"
        OTHER = "other", "Other"

    class Condition(models.TextChoices):
        ANY = "any", "Any condition"
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FULFILLED = "fulfilled", "Fulfilled"
        CLOSED = "closed", "Closed"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wanted_posts",
    )
    title = models.CharField(max_length=120)
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    preferred_condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.ANY,
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
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
