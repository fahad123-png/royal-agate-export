from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from django.db.models import F
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from django.utils.dateparse import parse_date

from apps.catalogue.models import Product
from apps.inventory.models import Inventory, StockMovement
from apps.inventory.serializers import (
    InventorySerializer,
    StockMovementSerializer,
    StockAdjustmentSerializer,
    StockAdjustmentResponseSerializer,
)
from apps.inventory.services import InventoryService


class AdminInventoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only API to view inventory records.
    """

    serializer_class = InventorySerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminInventoryPagination

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "product__name",
        "product__sku",
    ]

    ordering_fields = [
        "quantity",
        "low_stock_threshold",
        "created_at",
        "updated_at",
        "product__name",
    ]

    ordering = ["product__name"]

    def get_queryset(self):

        queryset = Inventory.objects.select_related(
            "product",
            "product__category"
        )

        stock_status = self.request.query_params.get("stock_status")

        if stock_status:
            stock_status = stock_status.upper()

            if stock_status == "IN_STOCK":
                queryset = queryset.filter(quantity__gt=0)

            elif stock_status == "LOW_STOCK":
                queryset = queryset.filter(
                    quantity__gt=0,
                    quantity__lte=F("low_stock_threshold")
                )

            elif stock_status == "OUT_OF_STOCK":
                queryset = queryset.filter(quantity=0)

            else:
                raise ValidationError({
                    "stock_status": "Invalid stock status."
                })

        category_id = self.request.query_params.get("category")

        if category_id:
            if not category_id.isdigit() or int(category_id) < 1:
                raise ValidationError({
                    "category": "Invalid category ID."
                })

            queryset = queryset.filter(
                product__category_id=int(category_id)
            )

        product_id = self.request.query_params.get("product")

        if product_id:
            if not product_id.isdigit() or int(product_id) < 1:
                raise ValidationError({
                    "product": "Invalid product ID."
                })

            queryset = queryset.filter(
                product_id=int(product_id)
            )

        return queryset


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only API to view stock movement history.
    """

    serializer_class = StockMovementSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminInventoryPagination

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "inventory__product__name",
        "inventory__product__sku",
        "reason",
    ]

    ordering_fields = [
        "created_at",
        "quantity",
        "stock_before",
        "stock_after",
        "movement_type",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):

        queryset = StockMovement.objects.select_related(
            "inventory",
            "inventory__product",
            "created_by"
        )

        movement_type = self.request.query_params.get(
            "movement_type"
        )

        if movement_type:
            movement_type = movement_type.upper()

            if movement_type not in StockMovement.MovementType.values:
                raise ValidationError({
                    "movement_type": "Invalid movement type."
                })

            queryset = queryset.filter(
                movement_type=movement_type
            )

        product_id = self.request.query_params.get("product")

        if product_id:
            if not product_id.isdigit() or int(product_id) < 1:
                raise ValidationError({
                    "product": "Invalid product ID."
                })

            queryset = queryset.filter(
                inventory__product_id=int(product_id)
            )

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if date_from:
            parsed_date_from = parse_date(date_from)

            if not parsed_date_from:
                raise ValidationError({
                    "date_from": "Invalid date. Use YYYY-MM-DD."
                })

            queryset = queryset.filter(
                created_at__date__gte=parsed_date_from
            )

        if date_to:
            parsed_date_to = parse_date(date_to)

            if not parsed_date_to:
                raise ValidationError({
                    "date_to": "Invalid date. Use YYYY-MM-DD."
                })

            queryset = queryset.filter(
                created_at__date__lte=parsed_date_to
            )

        if date_from and date_to and parsed_date_from > parsed_date_to:
            raise ValidationError({
                "date_to": "End date cannot be earlier than start date."
            })

        return queryset


class StockAdjustmentView(APIView):
    """
    Admin-only API to increase or decrease product stock.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        request=StockAdjustmentSerializer,
        responses={200: StockAdjustmentResponseSerializer}
    )


    def post(self, request):

        serializer = StockAdjustmentSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        product = get_object_or_404(
            Product,
            pk=serializer.validated_data["product_id"]
        )

        movement_type = serializer.validated_data["movement_type"]
        quantity = serializer.validated_data["quantity"]
        reason = serializer.validated_data.get("reason", "")

        if movement_type == StockMovement.MovementType.INCREASE:
            inventory = InventoryService.increase_stock(
                product=product,
                quantity=quantity,
                reason=reason,
                created_by=request.user
            )

        else:
            inventory = InventoryService.decrease_stock(
                product=product,
                quantity=quantity,
                reason=reason,
                created_by=request.user
            )

        return Response(
            {
                "message": "Stock adjusted successfully.",
                "inventory": InventorySerializer(inventory).data
            },
            status=status.HTTP_200_OK
        )

