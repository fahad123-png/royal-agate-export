from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalogue.models import Product


class Inventory(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory"
    )

    quantity = models.PositiveIntegerField(default=0)

    low_stock_threshold = models.PositiveIntegerField(
        default=5
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name"]
        verbose_name_plural = "Inventories"

    @property
    def is_in_stock(self):
        return self.quantity > 0

    @property
    def is_low_stock(self):
        return (
            self.quantity > 0
            and self.quantity <= self.low_stock_threshold
        )

    def __str__(self):
        return f"{self.product.name} - {self.quantity} units"


class StockMovement(models.Model):

    class MovementType(models.TextChoices):
        INCREASE = "INCREASE", "Stock Increase"
        DECREASE = "DECREASE", "Stock Decrease"

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.PROTECT,
        related_name="movements"
    )

    movement_type = models.CharField(
        max_length=10,
        choices=MovementType.choices
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    stock_before = models.PositiveIntegerField()

    stock_after = models.PositiveIntegerField()

    reason = models.CharField(
        max_length=255,
        blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            # Quantity must be at least 1.
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="stock_movement_quantity_gte_1"
            ),

            # Only valid movement types are allowed.
            models.CheckConstraint(
                condition=models.Q(
                    movement_type__in=["INCREASE", "DECREASE"]
                ),
                name="stock_movement_valid_type"
            ),

            # Stock values must match the movement operation.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        movement_type="INCREASE",
                        stock_after=(
                            models.F("stock_before")
                            + models.F("quantity")
                        )
                    )
                    |
                    models.Q(
                        movement_type="DECREASE",
                        stock_before__gte=models.F("quantity"),
                        stock_after=(
                            models.F("stock_before")
                            - models.F("quantity")
                        )
                    )
                ),
                name="stock_movement_values_consistent"
            ),
        ]

    def __str__(self):
        return (
            f"{self.movement_type} - "
            f"{self.inventory.product.name} - "
            f"{self.quantity}"
        )