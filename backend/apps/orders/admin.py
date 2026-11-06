from django.contrib import admin

from .models import Order, OrderItem, OrderCancellation


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False

    readonly_fields = (
        "product",
        "product_name",
        "product_sku",
        "purchase_mode",
        "quantity",
        "unit_price",
        "subtotal",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "order_number",
        "user",
        "total_amount",
        "status",
        "payment_status",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "created_at",
    )

    search_fields = (
        "order_number",
        "user__email",
        "user__username",
    )

    readonly_fields = (
        "order_number",
        "user",
        "subtotal",
        "shipping_charge",
        "discount",
        "total_amount",
        "created_at",
        "updated_at",
    )

    inlines = [OrderItemInline]

    ordering = ("-created_at",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderCancellation)
class OrderCancellationAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "requested_by",
        "status",
        "requested_at",
        "reviewed_by",
        "reviewed_at",
    )

    list_filter = (
        "status",
        "requested_at",
    )

    search_fields = (
        "order__order_number",
        "requested_by__email",
        "reason",
        "admin_note",
    )

    readonly_fields = (
        "order",
        "requested_by",
        "reason",
        "status",
        "admin_note",
        "reviewed_by",
        "requested_at",
        "reviewed_at",
    )

    ordering = ("-requested_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False