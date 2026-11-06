from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

from apps.content.models import ContentPage, FAQ, FAQCategory
from apps.content.serializers import (
    ContentPageSerializer,
    FAQSerializer,
)


# ==========================================
# PUBLIC: CONTENT PAGE LIST
# ==========================================

class ContentPageListView(generics.ListAPIView):

    serializer_class = ContentPageSerializer
    permission_classes = [AllowAny]

    queryset = ContentPage.objects.filter(
        is_published=True
    )


# ==========================================
# PUBLIC: CONTENT PAGE DETAIL
# ==========================================

class ContentPageDetailView(generics.RetrieveAPIView):

    serializer_class = ContentPageSerializer
    permission_classes = [AllowAny]

    lookup_field = "slug"

    queryset = ContentPage.objects.filter(
        is_published=True
    )


# ==========================================
# PUBLIC: FAQ LIST
# ==========================================

class FAQListView(generics.ListAPIView):

    serializer_class = FAQSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):

        queryset = FAQ.objects.filter(
            is_published=True,
            category__is_active=True,
        ).select_related("category")

        category_slug = self.request.query_params.get("category")

        if category_slug:

            if not FAQCategory.objects.filter(
                slug=category_slug,
                is_active=True,
            ).exists():

                raise ValidationError({
                    "category": "Invalid or inactive FAQ category."
                })

            queryset = queryset.filter(
                category__slug=category_slug
            )

        return queryset