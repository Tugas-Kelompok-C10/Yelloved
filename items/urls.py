from django.urls import path
from . import views

app_name = "items"

urlpatterns = [
    path("", views.explore_items, name="explore_items"),
]
