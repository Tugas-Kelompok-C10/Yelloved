from django.contrib import admin
from django.urls import include, path
from account_profile.views import AccountLoginView
from django.conf import settings
from django.conf.urls.static import static

from home.views import search_catalogue, send_love, show_main

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', AccountLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('explore/', include('items.urls')),
    path('transactions/', include('transactions.urls')),
    path('account/', include('account_profile.urls')),
    path('wanted-post/', include('wanted_board.urls')),
    path('item-matching/', include('item_matching.urls')),
    path("love/", send_love, name="send_love"),
    path("search/", search_catalogue, name="search_catalogue"),
    path("", show_main, name="show_main"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
