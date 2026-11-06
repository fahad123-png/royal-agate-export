from django.contrib import admin
from .models import CustomerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "get_email",
        "phone_number",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "phone_number",
    )

    list_filter = ("created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email