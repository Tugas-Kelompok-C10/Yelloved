from django.urls import path

from . import api, views

app_name = "account_profile"

urlpatterns = [
    path("api/profile/", api.profile_api, name="api_profile"),
    path("api/profile/photo/", api.profile_photo_api, name="api_profile_photo"),
    path("api/addresses/", api.addresses_api, name="api_addresses"),
    path("api/addresses/<int:address_id>/", api.address_detail_api, name="api_address_detail"),
    path("api/addresses/<int:address_id>/default/", api.address_default_api, name="api_address_default"),
    path("api/payment-methods/", api.payment_methods_api, name="api_payment_methods"),
    path("api/payment-methods/<int:method_id>/", api.payment_method_detail_api, name="api_payment_method_detail"),
    path("api/notifications/", api.notifications_api, name="api_notifications"),
    path("api/change-password/", api.change_password_api, name="api_change_password"),
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
    path("reviews/", views.profile_reviews, name="reviews"),
    path("help-messages/", views.help_messages, name="help_messages"),
    path("privacy/", views.privacy_security, name="privacy_security"),
]
