from django.urls import path

from home.views import show_main, show_activity, show_explore, show_wanted, register, show_account_profile

app_name = "home"

urlpatterns = [
    path("register/", register, name="register"),
    path("account-profile/", show_account_profile, name="account_profile"),
    path("", show_main, name="show_main"),
    path("", show_explore, name="show_explore"),
    path("", show_wanted, name="show_wanted"),
    path("", show_activity, name="show_activity"),
]
