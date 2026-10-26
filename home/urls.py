from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.conf.urls.static import static

from home.views import show_main

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view(template_name='account_profile/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('explore/', include('items.urls')),
    path('transactions/', include('transactions.urls')),
    path('account/', include('account_profile.urls')),
    path('wanted-post/', include('wanted_board.urls')),
    path('item-matching/', include('item_matching.urls')),
    path("", show_main, name="show_main"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
