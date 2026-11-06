from django.urls import path

from apps.content.views import (
    ContentPageListView,
    ContentPageDetailView,
    FAQListView,
)

urlpatterns = [
    # Public Content Pages
    path(
        "pages/",
        ContentPageListView.as_view(),
        name="content-page-list",
    ),

    path(
        "pages/<slug:slug>/",
        ContentPageDetailView.as_view(),
        name="content-page-detail",
    ),

    # Public FAQs
    path(
        "faqs/",
        FAQListView.as_view(),
        name="faq-list",
    ),
]