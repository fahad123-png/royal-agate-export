from rest_framework import serializers

from apps.content.models import ContentPage, FAQCategory, FAQ


class ContentPageSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContentPage

        fields = [
            "id",
            "title",
            "slug",
            "content",
            "seo_title",
            "seo_description",
            "updated_at",
        ]

        read_only_fields = fields


class FAQCategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = FAQCategory

        fields = [
            "id",
            "name",
            "slug",
        ]

        read_only_fields = fields


class FAQSerializer(serializers.ModelSerializer):

    category = FAQCategorySerializer(read_only=True)

    class Meta:
        model = FAQ

        fields = [
            "id",
            "category",
            "question",
            "answer",
            "sort_order",
            "updated_at",
        ]

        read_only_fields = fields