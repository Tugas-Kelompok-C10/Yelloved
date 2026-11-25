from django.urls import path

from . import api_views

# Mounted at item-matching/api/ by item_matching.urls; names stay in the item_matching namespace.
urlpatterns = [
    path('', api_views.dashboard, name='dashboard_api'),
    path('item/<int:item_id>/request/', api_views.request_create, name='request_create_api'),
    path('item/<int:item_id>/matches/', api_views.item_suggestions, name='item_suggestions_api'),
    path('wanted/<uuid:wanted_id>/offer-item/', api_views.offer_create, name='offer_create_api'),
    path('wanted/<uuid:pk>/matches/', api_views.wanted_suggestions, name='wanted_suggestions_api'),
    path('request/<int:pk>/accept/', api_views.request_accept, name='request_accept_api'),
    path('request/<int:pk>/reject/', api_views.request_reject, name='request_reject_api'),
    path('request/<int:pk>/cancel/', api_views.request_cancel, name='request_cancel_api'),
    path('offer/<int:pk>/accept/', api_views.offer_accept, name='offer_accept_api'),
    path('offer/<int:pk>/reject/', api_views.offer_reject, name='offer_reject_api'),
    path('offer/<int:pk>/withdraw/', api_views.offer_withdraw, name='offer_withdraw_api'),
]
