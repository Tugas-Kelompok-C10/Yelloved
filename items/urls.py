from django.urls import path
from . import views

app_name = 'items'
urlpatterns = [
    path('', views.explore_items, name='explore_items'),
    path('api/', views.items_json, name='items_json'),
    path('create/', views.item_create, name='item_create'),
    path('<int:item_id>/', views.item_detail, name='item_detail'),
    path('<int:item_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('<int:item_id>/edit/', views.item_update, name='item_update'),
    path('<int:item_id>/delete/', views.item_delete, name='item_delete'),
]
