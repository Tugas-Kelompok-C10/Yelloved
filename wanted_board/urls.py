from django.urls import path

from . import views

app_name = "wanted_board"

urlpatterns = [
    path("", views.show_wanted, name="show_wanted"),
    path("create/", views.create_wanted, name="create_wanted"),
    path(
        "sample/<slug:slug>/",
        views.sample_wanted_detail,
        name="sample_wanted_detail",
    ),
    path("<uuid:pk>/", views.wanted_detail, name="wanted_detail"),
    path("<uuid:pk>/edit/", views.edit_wanted, name="edit_wanted"),
    path("<uuid:pk>/delete/", views.delete_wanted, name="delete_wanted"),
    path("<uuid:pk>/status/", views.update_status, name="update_status"),
    path("<uuid:pk>/offer/", views.create_offer, name="create_offer"),
]
