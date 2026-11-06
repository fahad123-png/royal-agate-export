from decimal import Decimal

from rest_framework import serializers

from .models import Refund


class RefundCreateSerializer(serializers.Serializer):

    payment_id = serializers.IntegerField()

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    refund_method = serializers.ChoiceField(
        choices=Refund.RefundMethod.choices,
    )

    admin_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )


class RefundSerializer(serializers.ModelSerializer):

    order_number = serializers.CharField(
        source="payment.order.order_number",
        read_only=True,
    )

    payment_amount = serializers.DecimalField(
        source="payment.amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    payment_status = serializers.CharField(
        source="payment.status",
        read_only=True,
    )

    class Meta:
        model = Refund

        fields = (
            "id",
            "payment",
            "order_number",
            "payment_amount",
            "payment_status",
            "amount",
            "refund_method",
            "status",
            "transaction_reference",
            "admin_note",
            "processed_by",
            "completed_at",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields


class RefundCompleteSerializer(serializers.Serializer):

    transaction_reference = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=255,
        trim_whitespace=True,
    )

    admin_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )


class RefundFailSerializer(serializers.Serializer):

    admin_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )