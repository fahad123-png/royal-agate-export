from rest_framework import serializers

from apps.orders.models import Order


class CustomerDashboardProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField(allow_blank=True)


class CustomerDashboardStatisticsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    processing_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_spent = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )


class CustomerDashboardRecentOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "payment_status",
            "total_amount",
            "created_at",
        ]


class CustomerDashboardOverviewSerializer(serializers.Serializer):
    customer = CustomerDashboardProfileSerializer()
    statistics = CustomerDashboardStatisticsSerializer()
    recent_orders = CustomerDashboardRecentOrderSerializer(many=True)
    
from apps.payments.models import Refund


class CustomerRefundSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source="payment.order.order_number",
        read_only=True
    )

    class Meta:
        model = Refund
        fields = [
            "id",
            "order_number",
            "amount",
            "refund_method",
            "status",
            "transaction_reference",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields
        

class AdminDashboardSalesSerializer(serializers.Serializer):
    total_revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    today_revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    monthly_revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    total_refunded = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    net_revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )


class AdminDashboardOrderSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    processing_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    today_orders = serializers.IntegerField()
    monthly_orders = serializers.IntegerField()


class AdminDashboardProductSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    inactive_products = serializers.IntegerField()


class AdminDashboardInventorySerializer(serializers.Serializer):
    total_inventory_items = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()


class AdminDashboardPaymentSerializer(serializers.Serializer):
    total_payments = serializers.IntegerField()
    successful_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()


class AdminDashboardRefundSerializer(serializers.Serializer):
    pending_refunds = serializers.IntegerField()
    processing_refunds = serializers.IntegerField()
    completed_refunds = serializers.IntegerField()
    total_refunded = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )


class AdminDashboardOverviewSerializer(serializers.Serializer):
    sales = AdminDashboardSalesSerializer()
    orders = AdminDashboardOrderSerializer()
    products = AdminDashboardProductSerializer()
    inventory = AdminDashboardInventorySerializer()
    payments = AdminDashboardPaymentSerializer()
    refunds = AdminDashboardRefundSerializer()