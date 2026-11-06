from django.contrib import admin
from django.utils import timezone

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "product",
        "user",
        "rating",
        "status",
        "is_verified_purchase",
        "moderated_by",
        "created_at",
    )

    list_filter = (
        "status",
        "rating",
        "is_verified_purchase",
        "created_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "user__email",
        "user__first_name",
        "user__last_name",
        "title",
        "comment",
    )

    readonly_fields = (
        "user",
        "product",
        "rating",
        "title",
        "comment",
        "is_verified_purchase",
        "moderated_by",
        "moderated_at",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    list_per_page = 25

    fieldsets = (
        (
            "Review Information",
            {
                "fields": (
                    "user",
                    "product",
                    "rating",
                    "title",
                    "comment",
                    "is_verified_purchase",
                )
            },
        ),
        (
            "Moderation",
            {
                "fields": (
                    "status",
                    "moderated_by",
                    "moderated_at",
                    "moderation_note",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    
    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.moderated_by = request.user
            obj.moderated_at = timezone.now()

        super().save_model(request, obj, form, change)