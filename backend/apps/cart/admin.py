from django.contrib import admin
from .models import Cart, CartItem, CustomerAddress


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart",
        "product",
        "purchase_mode",
        "quantity",
        "created_at",
    )
    list_filter = ("purchase_mode", "created_at")
    search_fields = (
        "product__name",
        "product__sku",
        "cart__user__email",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "full_name",
        "city",
        "state",
        "is_default",
    )
    list_filter = ("is_default", "state", "country")
    search_fields = (
        "user__email",
        "full_name",
        "phone_number",
        "city",
        "pincode",
    )
    readonly_fields = ("created_at", "updated_at")