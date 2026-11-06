from django.urls import path

from apps.reviews.views import (
    ProductReviewListView,
    ProductRatingSummaryView,
    CustomerReviewCreateView,
    CustomerReviewListView,
    CustomerReviewDetailView,
    AdminReviewListView,
    AdminReviewModerationView,
)


urlpatterns = [

    # Public
    path(
        "product-reviews/",
        ProductReviewListView.as_view(),
        name="product-reviews"
    ),

    path(
        "products/<int:product_id>/rating-summary/",
        ProductRatingSummaryView.as_view(),
        name="product-rating-summary"
    ),

    # Customer
    path(
        "create/",
        CustomerReviewCreateView.as_view(),
        name="review-create"
    ),

    path(
        "my-reviews/",
        CustomerReviewListView.as_view(),
        name="my-reviews"
    ),

    path(
        "my-reviews/<int:pk>/",
        CustomerReviewDetailView.as_view(),
        name="my-review-detail"
    ),

    # Admin
    path(
        "admin/reviews/",
        AdminReviewListView.as_view(),
        name="admin-review-list"
    ),

    path(
        "admin/reviews/<int:pk>/moderate/",
        AdminReviewModerationView.as_view(),
        name="admin-review-moderate"
    ),
]