from django.contrib import admin
from .models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = (
        "image_url",
        "alt_text",
        "sort_order",
        "is_primary",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "retail_price",
        "wholesale_price",
        "is_active",
        "is_featured",
    )

    list_filter = ("category", "is_active", "is_featured")
    search_fields = ("name", "sku")
    ordering = ("-created_at",)

    inlines = [ProductImageInline]