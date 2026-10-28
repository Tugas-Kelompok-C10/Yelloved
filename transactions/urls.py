from django.urls import path
from . import views

app_name = "transactions"

urlpatterns = [
    path("", views.transaction_home, name="transaction_home"),

    path("checkout/", views.checkout, name="checkout"),

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

    path("history/", views.transaction_history, name="transaction_history"),
    path("app/", views.app_page, name="app"),
    path("pesan/", views.pesan_page, name="pesan"),
    path("cart/", views.cart_view, name="cart"),

    path(
        "cart/add/<int:item_id>/",
        views.add_to_cart,
        name="add_to_cart",
    ),
    path(
        "payment-preview/",
        views.payment_preview,
        name="payment_preview",
    ),
]