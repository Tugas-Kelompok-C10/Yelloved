from django.urls import path

from . import views

app_name = "account_profile"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("", views.show_account_profile, name="profile"),
]
