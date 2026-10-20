from django.urls import path

from . import views

app_name = "account_profile"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("", views.show_account_profile, name="profile"),
    path("addresses/", views.show_address_list, name="address_list"),
    path("addresses/<int:address_id>/edit/", views.edit_address, name="edit_address"),
    path("addresses/<int:address_id>/delete/", views.delete_address, name="delete_address"),
    path("addresses/<int:address_id>/default/", views.set_default_address, name="set_default_address"),
    path("payment/", views.show_payment_methods, name="payment_methods"),
    path("payment/<int:method_id>/edit/", views.edit_payment_method, name="edit_payment_method"),
    path("payment/<int:method_id>/delete/", views.delete_payment_method, name="delete_payment_method"),
    path("notifications/", views.notification_settings, name="notifications"),
    path("privacy/", views.privacy_security, name="privacy_security"),
]
