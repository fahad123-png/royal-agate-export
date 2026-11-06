from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Cart, CartItem, CustomerAddress


User = get_user_model()


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )
    product_slug = serializers.CharField(
        source="product.slug",
        read_only=True
    )
    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_slug",
            "product_sku",
            "product_image",
            "purchase_mode",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_product_image(self, obj):
        images = list(obj.product.images.all())

        if not images:
            return None

        primary_image = next(
            (image for image in images if image.is_primary),
            None
        )

        image = primary_image or images[0]

        return image.image_url

    def get_unit_price(self, obj):
        product = obj.product

        if obj.purchase_mode == CartItem.PurchaseMode.RETAIL:
            return product.retail_price

        if obj.purchase_mode == CartItem.PurchaseMode.WHOLESALE:
            return product.wholesale_price

        return None

    def get_subtotal(self, obj):
        unit_price = self.get_unit_price(obj)

        if unit_price is None:
            return None

        return unit_price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    total_items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_total_items(self, obj):
        return sum(
            item.quantity
            for item in obj.items.all()
        )

    def get_total_amount(self, obj):
        total = Decimal("0.00")

        for item in obj.items.all():
            unit_price = CartItemSerializer().get_unit_price(item)

            if unit_price is not None:
                total += unit_price * item.quantity

        return total


class CustomerAddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerAddress

        fields = [
            "id",
            "full_name",
            "phone_number",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "pincode",
            "country",
            "is_default",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_phone_number(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Phone number is required."
            )

        return value

    def validate_pincode(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Pincode is required."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user

        # Lock user row to serialize default-address changes.
        User.objects.select_for_update().get(pk=user.pk)

        is_default = validated_data.get("is_default", False)

        if is_default:
            CustomerAddress.objects.filter(
                user=user,
                is_default=True
            ).update(is_default=False)

        return CustomerAddress.objects.create(
            user=user,
            **validated_data
        )

    @transaction.atomic
    def update(self, instance, validated_data):

        # Lock user row before changing default address.
        User.objects.select_for_update().get(
            pk=instance.user_id
        )

        is_default = validated_data.get(
            "is_default",
            instance.is_default
        )

        if is_default:
            CustomerAddress.objects.filter(
                user=instance.user,
                is_default=True
            ).exclude(
                pk=instance.pk
            ).update(is_default=False)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance
    
# ==========================================
# CHECKOUT SERIALIZERS
# ==========================================

class CheckoutRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1)


class CheckoutPreviewItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(
        source="cart_item.product.id"
    )
    product_name = serializers.CharField(
        source="cart_item.product.name"
    )
    product_slug = serializers.CharField(
        source="cart_item.product.slug"
    )
    product_sku = serializers.CharField(
        source="cart_item.product.sku"
    )
    purchase_mode = serializers.CharField(
        source="cart_item.purchase_mode"
    )
    quantity = serializers.IntegerField(
        source="cart_item.quantity"
    )

    product_image = serializers.SerializerMethodField()

    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def get_product_image(self, obj):
        cart_item = obj["cart_item"]

        return CartItemSerializer().get_product_image(cart_item)


class CheckoutPreviewSerializer(serializers.Serializer):
    message = serializers.CharField()
    shipping_address = CustomerAddressSerializer(
        source="address"
    )
    items = CheckoutPreviewItemSerializer(many=True)
    total_items = serializers.IntegerField()
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )

