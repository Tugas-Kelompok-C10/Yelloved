from django.contrib import admin
from django.urls import include, path

from home.views import show_main

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('explore/', include('items.urls')),
    path('transactions/', include('transactions.urls')),
    path('account/', include('account_profile.urls')),
    path('wanted-post/', include('wanted_board.urls')),
    path("", show_main, name="show_main"),
]
