from django.urls import path

from apps.dashboard.views import (
     CustomerDashboardOverviewView,
     CustomerRefundListView,
     AdminDashboardOverviewView,
)


urlpatterns = [
    path(
        "customer/overview/",
        CustomerDashboardOverviewView.as_view(),
        name="customer-dashboard-overview",
    ),
    
    path(
        "customer/refunds/",
        CustomerRefundListView.as_view(),
        name="customer-refund-list"
    ),
    
    path(
        "admin/overview/",
        AdminDashboardOverviewView.as_view(),
        name="admin-dashboard-overview",
    ),
]