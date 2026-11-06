from rest_framework import serializers

from .models import (
    Order,
    OrderItem,
    OrderCancellation,
    OrderStatusHistory,
)


class OrderCreateSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000
    )


class OrderItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "purchase_mode",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "payment_status",
            "shipping_full_name",
            "shipping_phone_number",
            "shipping_address_line_1",
            "shipping_address_line_2",
            "shipping_city",
            "shipping_state",
            "shipping_pincode",
            "shipping_country",
            "subtotal",
            "shipping_charge",
            "discount",
            "total_amount",
            "notes",
            "items",
            "created_at",
            "shipped_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    order = OrderSerializer()
    
class CancellationRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=2000
    )


class CancellationReviewSerializer(serializers.Serializer):
    admin_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000
    )


class OrderCancellationSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source="order.order_number",
        read_only=True
    )

    order_status = serializers.CharField(
        source="order.status",
        read_only=True
    )

    class Meta:
        model = OrderCancellation
        fields = [
            "id",
            "order",
            "order_number",
            "order_status",
            "requested_by",
            "reason",
            "status",
            "admin_note",
            "reviewed_by",
            "requested_at",
            "reviewed_at",
        ]
        read_only_fields = fields
        
class OrderStatusUpdateSerializer(serializers.Serializer):

    status = serializers.ChoiceField(
        choices=Order.OrderStatus.choices,
        required=True
    )

    note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000
    )
    
class OrderStatusHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderStatusHistory
        fields = [
            "id",
            "previous_status",
            "new_status",
            "note",
            "changed_by",
            "created_at",
        ]
        read_only_fields = fields
        
class AdminOrderSerializer(OrderSerializer):
    customer_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    customer_name = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + [
            "customer_email",
            "customer_name",
        ]

    def get_customer_name(self, obj):
        return obj.shipping_full_name