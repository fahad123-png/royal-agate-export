from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer

from .models import Cart, CartItem, CustomerAddress
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    CustomerAddressSerializer,
    CheckoutRequestSerializer,
    CheckoutPreviewSerializer,
)
from .services import CartService


# ==========================================
# CART INPUT SERIALIZERS
# ==========================================

class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)

    purchase_mode = serializers.ChoiceField(
        choices=CartItem.PurchaseMode.choices
    )

    quantity = serializers.IntegerField(min_value=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


# ==========================================
# CART VIEWS
# ==========================================

class CartView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        cart = CartService.get_or_create_cart(request.user)

        cart = Cart.objects.prefetch_related(
            Prefetch(
                "items",
                queryset=CartItem.objects.select_related(
                    "product"
                ).prefetch_related(
                    "product__images"
                )
            )
        ).get(pk=cart.pk)

        serializer = CartSerializer(cart)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class CartItemAddView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item, created = CartService.add_item(
            user=request.user,
            product_id=serializer.validated_data["product_id"],
            purchase_mode=serializer.validated_data["purchase_mode"],
            quantity=serializer.validated_data["quantity"],
        )

        item = CartItem.objects.select_related(
            "product"
        ).prefetch_related(
            "product__images"
        ).get(pk=item.pk)

        response_serializer = CartItemSerializer(item)

        response_status = (
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        )

        message = (
            "Item added to cart successfully."
            if created
            else "Cart item quantity updated successfully."
        )

        return Response(
            {
                "message": message,
                "item": response_serializer.data,
            },
            status=response_status
        )


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def patch(self, request, item_id):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = CartService.update_item(
            user=request.user,
            item_id=item_id,
            quantity=serializer.validated_data["quantity"],
        )

        item = CartItem.objects.select_related(
            "product"
        ).prefetch_related(
            "product__images"
        ).get(pk=item.pk)

        return Response(
            {
                "message": "Cart item updated successfully.",
                "item": CartItemSerializer(item).data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, item_id):
        CartService.remove_item(
            user=request.user,
            item_id=item_id
        )

        return Response(
            {
                "message": "Cart item removed successfully."
            },
            status=status.HTTP_200_OK
        )


class CartClearView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def delete(self, request):
        CartService.clear_cart(request.user)

        return Response(
            {
                "message": "Cart cleared successfully."
            },
            status=status.HTTP_200_OK
        )


# ==========================================
# CUSTOMER ADDRESS VIEWS
# ==========================================

class CustomerAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        addresses = CustomerAddress.objects.filter(
            user=request.user
        ).order_by(
            "-is_default",
            "-updated_at"
        )

        serializer = CustomerAddressSerializer(
            addresses,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = CustomerAddressSerializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        address = serializer.save()

        return Response(
            {
                "message": "Address added successfully.",
                "address": CustomerAddressSerializer(address).data,
            },
            status=status.HTTP_201_CREATED
        )


class CustomerAddressDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_object(self, request, address_id):
        return get_object_or_404(
            CustomerAddress,
            pk=address_id,
            user=request.user
        )

    def get(self, request, address_id):
        address = self.get_object(request, address_id)

        serializer = CustomerAddressSerializer(address)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, address_id):
        address = self.get_object(request, address_id)

        serializer = CustomerAddressSerializer(
            address,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        address = serializer.save()

        return Response(
            {
                "message": "Address updated successfully.",
                "address": CustomerAddressSerializer(address).data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, address_id):
        address = self.get_object(request, address_id)
        address.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )
        
# ==========================================
# CHECKOUT PREVIEW VIEW
# ==========================================

class CheckoutPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        checkout_data = CartService.validate_checkout(
            user=request.user,
            address_id=serializer.validated_data["address_id"],
        )

        checkout_data["message"] = (
            "Checkout details validated successfully."
        )

        response_serializer = CheckoutPreviewSerializer(
            checkout_data
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK
        )