from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Payment(models.Model):

    class PaymentMethod(models.TextChoices):
        RAZORPAY = "RAZORPAY", "Razorpay"
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        OTHER = "OTHER", "Other"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments"
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    transaction_id = models.CharField(
        max_length=255,
        blank=True
    )

    gateway_order_id = models.CharField(
        max_length=255,
        blank=True
    )

    gateway_payment_id = models.CharField(
        max_length=255,
        blank=True
    )

    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["order", "-created_at"],
                name="payment_order_created_idx"
            ),
            models.Index(
                fields=["status"],
                name="payment_status_idx"
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_gt_0"
            ),
        ]

        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment - {self.order.order_number}"
    
class Refund(models.Model):

    class RefundMethod(models.TextChoices):
        UPI = "UPI", "UPI"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"

    class RefundStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    refund_method = models.CharField(
        max_length=20,
        choices=RefundMethod.choices,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
    )

    transaction_reference = models.CharField(
        max_length=255,
        blank=True,
    )

    admin_note = models.TextField(blank=True)

    processed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["payment", "-created_at"],
                name="refund_payment_created_idx",
            ),
            models.Index(
                fields=["status"],
                name="refund_status_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="refund_amount_gt_0",
            ),
        ]

        verbose_name = "Refund"
        verbose_name_plural = "Refunds"

    def __str__(self):
        return f"Refund - {self.payment.order.order_number}"