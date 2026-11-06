from rest_framework import serializers

from apps.inventory.models import Inventory, StockMovement


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True
    )

    is_in_stock = serializers.BooleanField(read_only=True)

    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "low_stock_threshold",
            "is_in_stock",
            "is_low_stock",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "product",
            "quantity",
            "low_stock_threshold",
            "created_at",
            "updated_at",
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="inventory.product.name",
        read_only=True
    )

    product_sku = serializers.CharField(
        source="inventory.product.sku",
        read_only=True
    )

    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True
    )

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "inventory",
            "product_name",
            "product_sku",
            "movement_type",
            "quantity",
            "stock_before",
            "stock_after",
            "reason",
            "created_by",
            "created_by_email",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "inventory",
            "movement_type",
            "quantity",
            "stock_before",
            "stock_after",
            "reason",
            "created_by",
            "created_at",
        ]


class StockAdjustmentSerializer(serializers.Serializer):

    

    product_id = serializers.IntegerField(
        min_value=1
    )

    movement_type = serializers.ChoiceField(
        choices=StockMovement.MovementType.choices
    )

    quantity = serializers.IntegerField(
        min_value=1
    )

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255
    )

class StockAdjustmentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    inventory = InventorySerializer()
