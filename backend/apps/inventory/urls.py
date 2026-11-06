from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import (
    InventoryViewSet,
    StockMovementViewSet,
    StockAdjustmentView,
)

router = DefaultRouter()

router.register(
    r"stock",
    InventoryViewSet,
    basename="inventory"
)

router.register(
    r"movements",
    StockMovementViewSet,
    basename="stock-movement"
)

urlpatterns = [
    path(
        "adjust/",
        StockAdjustmentView.as_view(),
        name="stock-adjustment"
    ),
]

urlpatterns += router.urls

