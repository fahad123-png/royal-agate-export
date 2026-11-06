from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from .models import Category, Product, ProductImage
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductDetailSerializer,
    AdminProductImageSerializer,
)
from .pagination import CataloguePagination
from .filters import ProductFilter


class CategoryViewSet(viewsets.ModelViewSet):

    serializer_class = CategorySerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Category.objects.all().order_by("sort_order", "name")

        return Category.objects.filter(is_active=True).order_by(
            "sort_order", "name"
        )

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        return [IsAdminUser()]


class ProductViewSet(viewsets.ModelViewSet):

    serializer_class = ProductSerializer
    pagination_class = CataloguePagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = ProductFilter

    search_fields = [
        "name",
        "sku",
        "description",
    ]

    ordering_fields = [
        "name",
        "retail_price",
        "created_at",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Product.objects.select_related(
            "category",
            "inventory"
        ).prefetch_related(
            "images"
        )

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(is_active=True)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer

        return ProductSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        return [IsAdminUser()]
    
class ProductImageViewSet(viewsets.ModelViewSet):

    serializer_class = AdminProductImageSerializer
    permission_classes = [IsAdminUser]

    queryset = ProductImage.objects.select_related(
        "product"
    ).all()