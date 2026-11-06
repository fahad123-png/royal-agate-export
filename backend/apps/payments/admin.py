from django.contrib import admin

from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "order",
        "payment_method",
        "amount",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
        "created_at",
    )

    search_fields = (
        "order__order_number",
        "transaction_id",
        "gateway_order_id",
        "gateway_payment_id",
    )

    readonly_fields = (
        "order",
        "payment_method",
        "amount",
        "transaction_id",
        "gateway_order_id",
        "gateway_payment_id",
        "failure_reason",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "payment",
        "amount",
        "refund_method",
        "status",
        "transaction_reference",
        "processed_by",
        "created_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "refund_method",
        "created_at",
    )

    search_fields = (
        "payment__order__order_number",
        "transaction_reference",
        "payment__transaction_id",
        "admin_note",
    )

    readonly_fields = (
        "payment",
        "amount",
        "refund_method",
        "status",
        "transaction_reference",
        "admin_note",
        "processed_by",
        "completed_at",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False