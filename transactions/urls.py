from django.urls import path
from django.views.generic import RedirectView
from . import views, api
from .wanted import wanted_detail


app_name = "transactions"

urlpatterns = [
    path("wanted/<str:order_id>/", wanted_detail, name="wanted_detail"),
    path(
        "",
        views.transaction_home,
        name="transaction_home",
    ),

    path(
        "checkout/",
        views.checkout,
        name="checkout",
    ),

    path(
        "checkout/success-preview/",
        views.checkout_success_preview,
        name="checkout_success_preview",
    ),

    path(
        "checkout/success/<str:order_id>/cancel/",
        views.cancel_order,
        name="cancel_order",
    ),

    path(
        "checkout/success/<str:order_id>/",
        views.checkout_success,
        name="checkout_success",
    ),

    path(
        "history/",
        views.transaction_history,
        name="transaction_history",
    ),

    path(
        "app/",
        views.app_page,
        name="app",
    ),

    path(
        "pesan/",
        RedirectView.as_view(pattern_name="chat:inbox", permanent=False),
        name="pesan",
    ),

    path(
        "cart/",
        views.cart_view,
        name="cart",
    ),

    path(
        "cart/add/<int:item_id>/",
        views.add_to_cart,
        name="add_to_cart",
    ),

    path(
        "cart/remove/<int:entry_id>/",
        views.remove_from_cart,
        name="remove_from_cart",
    ),

    path(
        "payment-preview/",
        views.payment_preview,
        name="payment_preview",
    ),

    path(
        "midtrans/notification/",
        views.midtrans_notification,
        name="midtrans_notification",
    ),

    path(
        "api/cart/",
        api.cart_api,
        name="cart_api",
    ),

    path(
        "api/addresses/",
        api.address_list_api,
        name="address_list_api",
    ),

    path(
        "api/checkout/cod/",
        api.checkout_cod_api,
        name="checkout_cod_api",
    ),

    path(
        "api/checkout/qris/",
        api.checkout_qris_api,
        name="checkout_qris_api",
    ),

    path(
        "api/history/",
        api.transaction_history_api,
        name="transaction_history_api",
    ),

    path(
        "api/checkout/va/",
        api.checkout_va_api,
        name="checkout_va_api",
    ),

    path(
        "api/<str:order_id>/qris-image/",
        api.transaction_qris_image_api,
        name="transaction_qris_image_api",
    ),



    path(
        "api/<str:order_id>/",
        api.transaction_detail_api,
        name="transaction_detail_api",
    ),

    path(
        "api/cart/add/<int:item_id>/",
        api.add_cart_api,
        name="add_cart_api",
    ),

    path(
        "api/cart/update/<int:cart_item_id>/",
        api.update_cart_api,
        name="update_cart_api",
    ),

    path(
        "api/cart/<int:cart_item_id>/",
        api.remove_cart_api,
        name="remove_cart_api",
    ),

    path(
        "api/",
        views.TransactionListAPIView.as_view(),
        name="transaction_api",
    ),
]
