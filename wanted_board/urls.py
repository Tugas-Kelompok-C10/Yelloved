from django.urls import path

from . import views

app_name = "wanted_board"

urlpatterns = [
    path("", views.show_wanted, name="show_wanted"),
    path("create/", views.create_wanted, name="create_wanted"),
    path(
        "sample/<slug:slug>/poster/",
        views.sample_poster_profile,
        name="sample_poster_profile",
    ),
    path(
        "sample/<slug:slug>/",
        views.sample_wanted_detail,
        name="sample_wanted_detail",
    ),
    path("<int:pk>/", views.wanted_detail, name="wanted_detail"),
    path("<int:pk>/edit/", views.edit_wanted, name="edit_wanted"),
    path("<int:pk>/delete/", views.delete_wanted, name="delete_wanted"),
    path("<int:pk>/status/", views.update_status, name="update_status"),
    path("<int:pk>/offer/", views.create_offer, name="create_offer"),
]
