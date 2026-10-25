from django.urls import path
from . import views
from .views import (
    transaction_home,
    checkout,
    transaction_history,
    app_page,
)

app_name = "transactions"

urlpatterns = [
    path("", views.transaction_home, name="transaction_home"),
    path("checkout/", views.checkout, name="checkout"),
    path("history/", views.transaction_history, name="transaction_history"),
    path("app/", app_page, name="app"),
    path("pesan/", views.pesan_page, name="pesan"),
]
