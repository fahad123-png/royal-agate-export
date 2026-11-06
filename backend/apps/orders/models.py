from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from decimal import Decimal


class Order(models.Model):

    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PROCESSING = "PROCESSING", "Processing"
        SHIPPED = "SHIPPED", "Shipped"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    order_number = models.CharField(
        max_length=32,
        unique=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders"
    )

    # Shipping address snapshot
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone_number = models.CharField(max_length=20)
    shipping_address_line_1 = models.CharField(max_length=255)
    shipping_address_line_2 = models.CharField(
        max_length=255,
        blank=True
    )
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)
    shipping_country = models.CharField(
        max_length=100,
        default="India"
    )

    # Order amounts
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    shipping_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    
    stock_deducted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    stock_restored_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    shipped_at = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="order_user_created_idx"
            ),
            models.Index(
                fields=["status"],
                name="order_status_idx"
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="order_subtotal_gte_0"
            ),
            models.CheckConstraint(
                condition=Q(shipping_charge__gte=0),
                name="order_shipping_gte_0"
            ),
            models.CheckConstraint(
                condition=Q(discount__gte=0),
                name="order_discount_gte_0"
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="order_total_gte_0"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "PENDING",
                        "CONFIRMED",
                        "PROCESSING",
                        "SHIPPED",
                        "CANCELLED",
                    ]
                ),
                name="order_valid_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    payment_status__in=[
                        "PENDING",
                        "PAID",
                        "FAILED",
                    ]
                ),
                name="order_valid_payment_status",
            ),
        ]

        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):

    class PurchaseMode(models.TextChoices):
        RETAIL = "RETAIL", "Retail"
        WHOLESALE = "WHOLESALE", "Wholesale"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "catalogue.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    # Product purchase-time snapshots
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)

    purchase_mode = models.CharField(
        max_length=10,
        choices=PurchaseMode.choices
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_item_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=0),
                name="order_item_price_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gt=0),
                name="order_item_subtotal_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(
                    purchase_mode__in=["RETAIL", "WHOLESALE"]
                ),
                name="order_item_valid_purchase_mode",
            ),
            models.CheckConstraint(
                condition=Q(subtotal=F("unit_price") * F("quantity")),
                name="order_item_subtotal_matches_price_qty",
            ),
        ]

        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
    
class OrderCancellation(models.Model):

    class CancellationStatus(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        DIRECT_CANCELLED = "DIRECT_CANCELLED", "Directly Cancelled"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="cancellations"
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="order_cancellations"
    )

    reason = models.TextField()

    status = models.CharField(
        max_length=25,
        choices=CancellationStatus.choices,
        default=CancellationStatus.REQUESTED
    )

    admin_note = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_order_cancellations"
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-requested_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status="REQUESTED"),
                name="unique_active_order_cancellation"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "REQUESTED",
                        "DIRECT_CANCELLED",
                        "APPROVED",
                        "REJECTED",
                    ]
                ),
                name="order_cancellation_valid_status",
            ),
        ]

        verbose_name = "Order Cancellation"
        verbose_name_plural = "Order Cancellations"

    def __str__(self):
        return (
            f"{self.order.order_number} - "
            f"{self.status}"
        )
        
class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history"
    )
    previous_status = models.CharField(
        max_length=20,
        blank=True
    )
    new_status = models.CharField(
        max_length=20,
        choices=Order.OrderStatus.choices
    )
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    new_status__in=[
                        "PENDING",
                        "CONFIRMED",
                        "PROCESSING",
                        "SHIPPED",
                        "CANCELLED",
                    ]
                ),
                name="order_history_valid_new_status",
            ),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.new_status}"