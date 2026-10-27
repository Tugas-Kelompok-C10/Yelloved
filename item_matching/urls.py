from django.urls import path

from . import views

app_name = 'item_matching'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('item/<int:item_id>/request/', views.request_create, name='request_create'),
    path('item/<int:item_id>/matches/', views.item_suggestions, name='item_suggestions'),
    path('wanted/<uuid:wanted_id>/offer-item/', views.offer_create, name='offer_create'),
    path('wanted/<uuid:pk>/matches/', views.wanted_suggestions, name='wanted_suggestions'),
    path('request/<int:pk>/accept/', views.request_accept, name='request_accept'),
    path('request/<int:pk>/reject/', views.request_reject, name='request_reject'),
    path('request/<int:pk>/cancel/', views.request_cancel, name='request_cancel'),
    path('offer/<int:pk>/accept/', views.offer_accept, name='offer_accept'),
    path('offer/<int:pk>/reject/', views.offer_reject, name='offer_reject'),
    path('offer/<int:pk>/withdraw/', views.offer_withdraw, name='offer_withdraw'),
]
