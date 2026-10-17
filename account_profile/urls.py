from django.urls import path

from . import views

app_name = "account_profile"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("", views.show_account_profile, name="profile"),
    path("addresses/", views.show_address_list, name="address_list"),
    path("addresses/<int:address_id>/edit/", views.edit_address, name="edit_address"),
    path("addresses/<int:address_id>/delete/", views.delete_address, name="delete_address"),
]
