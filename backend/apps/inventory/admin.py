from django.contrib import admin

from apps.inventory.models import Inventory, StockMovement


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "product",
        "quantity",
        "low_stock_threshold",
        "is_in_stock",
        "is_low_stock",
        "updated_at",
    )

    list_filter = (
        "quantity",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
    )

    readonly_fields = (
        "quantity",
        "created_at",
        "updated_at",
    )

    ordering = ("product__name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "inventory",
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "created_by",
        "created_at",
    )

    list_filter = (
        "movement_type",
        "created_at",
    )

    search_fields = (
        "inventory__product__name",
        "inventory__product__sku",
        "reason",
    )

    readonly_fields = (
        "inventory",
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "reason",
        "created_by",
        "created_at",
    )

    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

