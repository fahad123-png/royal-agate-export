from django.urls import path

from .views import (
    CartView,
    CartItemAddView,
    CartItemDetailView,
    CartClearView,
    CustomerAddressListCreateView,
    CustomerAddressDetailView,
    CheckoutPreviewView,
)


urlpatterns = [

    # ======================================
    # CART ENDPOINTS
    # ======================================

    path(
        "",
        CartView.as_view(),
        name="cart-detail"
    ),

    path(
        "items/",
        CartItemAddView.as_view(),
        name="cart-item-add"
    ),

    path(
        "items/<int:item_id>/",
        CartItemDetailView.as_view(),
        name="cart-item-detail"
    ),

    path(
        "clear/",
        CartClearView.as_view(),
        name="cart-clear"
    ),

    # ======================================
    # CUSTOMER ADDRESS ENDPOINTS
    # ======================================

    path(
        "addresses/",
        CustomerAddressListCreateView.as_view(),
        name="address-list-create"
    ),

    path(
        "addresses/<int:address_id>/",
        CustomerAddressDetailView.as_view(),
        name="address-detail"
    ),
    
    path(
        "checkout/preview/",
        CheckoutPreviewView.as_view(),
        name="checkout-preview"
    ),

]