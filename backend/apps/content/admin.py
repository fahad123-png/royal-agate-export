from django.contrib import admin

from apps.content.models import ContentPage, FAQCategory, FAQ


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "slug",
        "is_published",
        "updated_by",
        "updated_at",
    )

    list_filter = (
        "is_published",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "slug",
        "content",
        "seo_title",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "updated_by",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    list_editable = ("is_published",)

    ordering = ("title",)

    list_per_page = 25

    fieldsets = (
        (
            "Page Information",
            {
                "fields": (
                    "title",
                    "slug",
                    "content",
                    "is_published",
                )
            },
        ),
        (
            "SEO Settings",
            {
                "fields": (
                    "seo_title",
                    "seo_description",
                )
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "updated_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "slug",
        "is_active",
        "sort_order",
    )

    list_filter = ("is_active",)

    search_fields = ("name", "slug")

    prepopulated_fields = {
        "slug": ("name",),
    }

    list_editable = (
        "is_active",
        "sort_order",
    )

    ordering = ("sort_order", "name")

    list_per_page = 25


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "question",
        "category",
        "is_published",
        "sort_order",
        "updated_by",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_published",
        "created_at",
    )

    search_fields = (
        "question",
        "answer",
        "category__name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "updated_by",
    )

    list_editable = (
        "is_published",
        "sort_order",
    )

    ordering = ("sort_order", "id")

    list_per_page = 25

    fieldsets = (
        (
            "FAQ Information",
            {
                "fields": (
                    "category",
                    "question",
                    "answer",
                    "is_published",
                    "sort_order",
                )
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "updated_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)