from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.throttling import ScopedRateThrottle

from apps.common.permissions import IsAdmin
from apps.contact.models import ContactInquiry
from apps.contact.serializers import (
    ContactInquiryCreateSerializer,
    ContactInquiryAdminSerializer,
)


# ==========================================
# PUBLIC: SUBMIT CONTACT INQUIRY
# ==========================================

class ContactInquiryCreateView(generics.CreateAPIView):

    queryset = ContactInquiry.objects.all()

    serializer_class = ContactInquiryCreateSerializer

    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]

    throttle_scope = "contact_inquiry"


# ==========================================
# ADMIN: LIST ALL INQUIRIES
# ==========================================

class AdminContactInquiryListView(generics.ListAPIView):

    serializer_class = ContactInquiryAdminSerializer

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "name",
        "email",
        "phone",
        "subject",
        "message",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "status",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):

        queryset = ContactInquiry.objects.all()

        inquiry_status = self.request.query_params.get("status")

        if inquiry_status:

            valid_statuses = [
                choice[0]
                for choice in ContactInquiry.InquiryStatus.choices
            ]

            if inquiry_status not in valid_statuses:
                raise ValidationError({
                    "status": "Invalid inquiry status."
                })

            queryset = queryset.filter(status=inquiry_status)

        return queryset


# ==========================================
# ADMIN: VIEW / UPDATE INQUIRY
# ==========================================

class AdminContactInquiryDetailView(generics.RetrieveUpdateAPIView):

    serializer_class = ContactInquiryAdminSerializer

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    queryset = ContactInquiry.objects.all()