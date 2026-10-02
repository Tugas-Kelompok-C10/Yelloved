from django.urls import path

from . import views

app_name = "wanted_board"

urlpatterns = [
    path("", views.show_wanted, name="show_wanted"),
]
