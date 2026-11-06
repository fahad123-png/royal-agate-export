from django.urls import path

from apps.contact.views import (
    ContactInquiryCreateView,
    AdminContactInquiryListView,
    AdminContactInquiryDetailView,
)


urlpatterns = [

    # Public
    path(
        "submit/",
        ContactInquiryCreateView.as_view(),
        name="contact-submit"
    ),

    # Admin
    path(
        "admin/inquiries/",
        AdminContactInquiryListView.as_view(),
        name="admin-contact-inquiry-list"
    ),

    path(
        "admin/inquiries/<int:pk>/",
        AdminContactInquiryDetailView.as_view(),
        name="admin-contact-inquiry-detail"
    ),

]