from django.urls import path
from . import views

app_name = "transactions"

urlpatterns = [
    path("", views.transaction_home, name="transaction_home"),
    path("checkout/", views.checkout, name="checkout"),
    path("history/", views.transaction_history, name="transaction_history"),
]