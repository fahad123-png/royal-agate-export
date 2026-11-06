from django.urls import path

from .views import (
    OrderCreateView,
    OrderListView,
    OrderDetailView,
    AdminOrderConfirmView,
    CustomerOrderCancelView,
    CustomerCancellationListView,
    AdminCancellationListView,
    AdminCancellationApproveView,
    AdminCancellationRejectView,
    AdminOrderStatusUpdateView,
    CustomerOrderTimelineView,
    AdminOrderListView,
    AdminOrderDetailView,
)


urlpatterns = [
    
    
    # Admin Order Management

    path(
        "admin/",
        AdminOrderListView.as_view(),
        name="admin-order-list",
    ),

    path(
        "admin/<int:pk>/",
        AdminOrderDetailView.as_view(),
        name="admin-order-detail",
    ),

    # Create Order
    path(
        "",
        OrderCreateView.as_view(),
        name="order-create"
    ),

    # Customer Order List
    path(
        "my-orders/",
        OrderListView.as_view(),
        name="order-list"
    ),

    # Customer Cancellation History
    path(
        "my-cancellations/",
        CustomerCancellationListView.as_view(),
        name="customer-cancellation-list"
    ),

    # Admin Cancellation Management
    path(
        "admin/cancellations/",
        AdminCancellationListView.as_view(),
        name="admin-cancellation-list"
    ),

    path(
        "admin/cancellations/<int:pk>/approve/",
        AdminCancellationApproveView.as_view(),
        name="admin-cancellation-approve"
    ),

    path(
        "admin/cancellations/<int:pk>/reject/",
        AdminCancellationRejectView.as_view(),
        name="admin-cancellation-reject"
    ),

    # Admin Order Confirmation
    path(
        "<int:pk>/confirm/",
        AdminOrderConfirmView.as_view(),
        name="admin-order-confirm"
    ),
    
    # Admin Order Status Update
    path(
        "<int:pk>/status/",
        AdminOrderStatusUpdateView.as_view(),
        name="admin-order-status-update"
    ),

    # Customer Order Cancellation
    path(
        "<int:pk>/cancel/",
        CustomerOrderCancelView.as_view(),
        name="order-cancel"
    ),

    # Customer Order Detail
    path(
        "<int:pk>/",
        OrderDetailView.as_view(),
        name="order-detail"
    ),
    
    # Customer Order Timeline
    path(
        "<int:pk>/timeline/",
        CustomerOrderTimelineView.as_view(),
        name="order-timeline"
    ),

]