from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .models import Payment, Refund


class RefundService:

    ACTIVE_REFUND_STATUSES = [
        Refund.RefundStatus.PENDING,
        Refund.RefundStatus.PROCESSING,
        Refund.RefundStatus.COMPLETED,
    ]

    @staticmethod
    @transaction.atomic
    def create_refund(
        payment_id,
        amount,
        refund_method,
        admin_user,
        admin_note="",
    ):
        try:
            payment = (
                Payment.objects
                .select_for_update()
                .select_related("order")
                .get(id=payment_id)
            )
        except Payment.DoesNotExist:
            raise ValidationError("Payment not found.")

        if payment.order.status != "CANCELLED":
            raise ValidationError(
                "Refund can only be created for cancelled orders."
            )

        if payment.status != Payment.PaymentStatus.SUCCESS:
            raise ValidationError(
                "Only successful payments can be refunded."
            )

        if refund_method not in Refund.RefundMethod.values:
            raise ValidationError("Invalid refund method.")

        try:
            amount = Decimal(str(amount))
        except Exception:
            raise ValidationError("Invalid refund amount.")

        if not amount.is_finite() or amount <= Decimal("0.00"):
            raise ValidationError("Refund amount must be greater than zero.")

        reserved_amount = (
            Refund.objects
            .filter(
                payment=payment,
                status__in=RefundService.ACTIVE_REFUND_STATUSES,
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        remaining_amount = payment.amount - reserved_amount

        if amount > remaining_amount:
            raise ValidationError(
                f"Refund amount exceeds the remaining refundable amount "
                f"of {remaining_amount}."
            )

        return Refund.objects.create(
            payment=payment,
            amount=amount,
            refund_method=refund_method,
            status=Refund.RefundStatus.PENDING,
            admin_note=admin_note,
            processed_by=admin_user,
        )

    @staticmethod
    @transaction.atomic
    def start_refund(refund_id, admin_user):
        try:
            refund = Refund.objects.select_for_update().get(
                id=refund_id
            )
        except Refund.DoesNotExist:
            raise ValidationError("Refund not found.")

        if refund.status != Refund.RefundStatus.PENDING:
            raise ValidationError(
                "Only pending refunds can be moved to processing."
            )

        refund.status = Refund.RefundStatus.PROCESSING
        refund.processed_by = admin_user

        refund.save(
            update_fields=[
                "status",
                "processed_by",
                "updated_at",
            ]
        )

        return refund

    @staticmethod
    @transaction.atomic
    def complete_refund(
        refund_id,
        transaction_reference,
        admin_user,
        admin_note=None,
    ):
        try:
            refund = Refund.objects.select_for_update().get(
                id=refund_id
            )
        except Refund.DoesNotExist:
            raise ValidationError("Refund not found.")

        if refund.status != Refund.RefundStatus.PROCESSING:
            raise ValidationError(
                "Only processing refunds can be completed."
            )

        transaction_reference = transaction_reference.strip()

        if not transaction_reference:
            raise ValidationError(
                "Transaction reference is required."
            )

        refund.status = Refund.RefundStatus.COMPLETED
        refund.transaction_reference = transaction_reference
        refund.processed_by = admin_user
        refund.completed_at = timezone.now()

        if admin_note is not None:
            refund.admin_note = admin_note

        refund.save()

        return refund

    @staticmethod
    @transaction.atomic
    def fail_refund(
        refund_id,
        admin_user,
        admin_note="",
    ):
        try:
            refund = Refund.objects.select_for_update().get(
                id=refund_id
            )
        except Refund.DoesNotExist:
            raise ValidationError("Refund not found.")

        if refund.status not in [
            Refund.RefundStatus.PENDING,
            Refund.RefundStatus.PROCESSING,
        ]:
            raise ValidationError(
                "Only pending or processing refunds can be marked as failed."
            )

        refund.status = Refund.RefundStatus.FAILED
        refund.processed_by = admin_user
        refund.admin_note = admin_note

        refund.save(
            update_fields=[
                "status",
                "processed_by",
                "admin_note",
                "updated_at",
            ]
        )

        return refund