from django.urls import path

from .views import (
    RefundListCreateView,
    RefundProcessView,
    RefundCompleteView,
    RefundFailView,
)


urlpatterns = [
    path(
        "refunds/",
        RefundListCreateView.as_view(),
        name="refund-list-create",
    ),
    path(
        "refunds/<int:pk>/process/",
        RefundProcessView.as_view(),
        name="refund-process",
    ),
    path(
        "refunds/<int:pk>/complete/",
        RefundCompleteView.as_view(),
        name="refund-complete",
    ),
    path(
        "refunds/<int:pk>/fail/",
        RefundFailView.as_view(),
        name="refund-fail",
    ),
]