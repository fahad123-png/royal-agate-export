from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q


class Review(models.Model):

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    # Review author
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews"
    )

    # Reviewed product
    product = models.ForeignKey(
        "catalogue.Product",
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    # Review details
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    title = models.CharField(
        max_length=150,
        blank=True
    )

    comment = models.TextField()

    # Purchase verification
    is_verified_purchase = models.BooleanField(
        default=False
    )

    # Moderation
    status = models.CharField(
        max_length=10,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING
    )

    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews"
    )

    moderated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    moderation_note = models.TextField(
        blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_review"
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="review_rating_1_to_5"
            ),
        ]

        indexes = [
            models.Index(
                fields=["product", "status"],
                name="review_product_status_idx"
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="review_user_created_idx"
            ),
        ]

        verbose_name = "Product Review"
        verbose_name_plural = "Product Reviews"

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.user.email} ({self.rating}/5)"
        )