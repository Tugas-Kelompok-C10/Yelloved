from django.urls import path

from .api_views import ItemListView

app_name = 'items_api'

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
]
