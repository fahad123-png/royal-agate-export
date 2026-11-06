from django.contrib import admin

from apps.contact.models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "subject",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "subject",
        "message",
    )

    readonly_fields = (
        "name",
        "email",
        "phone",
        "subject",
        "message",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)

    list_per_page = 25

    fieldsets = (
        (
            "Customer Information",
            {
                "fields": (
                    "name",
                    "email",
                    "phone",
                )
            },
        ),
        (
            "Inquiry Details",
            {
                "fields": (
                    "subject",
                    "message",
                )
            },
        ),
        (
            "Admin Management",
            {
                "fields": (
                    "status",
                    "admin_notes",
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