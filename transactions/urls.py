from django.urls import path
from django.views.generic import RedirectView
from . import views
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
]
