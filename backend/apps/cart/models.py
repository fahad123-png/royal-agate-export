from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    """
    One active cart per customer.
    Cart remains saved even after logout.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart - {self.user}"


class CartItem(models.Model):
    """
    Individual products stored inside a customer's cart.
    The same product can exist in both RETAIL and WHOLESALE modes.
    """

    class PurchaseMode(models.TextChoices):
        RETAIL = "RETAIL", "Retail"
        WHOLESALE = "WHOLESALE", "Wholesale"

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "catalogue.Product",
        on_delete=models.PROTECT,
        related_name="cart_items"
    )

    purchase_mode = models.CharField(
        max_length=10,
        choices=PurchaseMode.choices
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product", "purchase_mode"],
                name="unique_product_mode_per_cart"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="cart_item_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=Q(
                    purchase_mode__in=["RETAIL", "WHOLESALE"]
                ),
                name="cart_item_valid_purchase_mode"
            ),
        ]

        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.purchase_mode} - "
            f"{self.quantity}"
        )


class CustomerAddress(models.Model):
    """
    Stores multiple delivery addresses for each customer.
    Only one address can be default per customer.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses"
    )

    full_name = models.CharField(max_length=150)

    phone_number = models.CharField(max_length=20)

    address_line_1 = models.CharField(max_length=255)

    address_line_2 = models.CharField(
        max_length=255,
        blank=True
    )

    city = models.CharField(max_length=100)

    state = models.CharField(max_length=100)

    pincode = models.CharField(max_length=10)

    country = models.CharField(
        max_length=100,
        default="India"
    )

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="unique_default_address_per_user"
            )
        ]

        verbose_name = "Customer Address"
        verbose_name_plural = "Customer Addresses"

    def __str__(self):
        return f"{self.full_name} - {self.city}"