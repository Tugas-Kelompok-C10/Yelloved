from django.urls import path

from . import views

app_name = "chat"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("inbox-data/", views.inbox_api, name="inbox_data"),
    path("notifications/", views.notifications, name="notifications"),
    path("with/<int:user_id>/read/", views.mark_read, name="mark_read"),
    path("attachments/<uuid:pk>/", views.attachment, name="attachment"),
    path("with/<int:user_id>/", views.with_user, name="with_user"),
    path("with/<int:user_id>/messages/", views.messages_api, name="messages"),
    path("messages/<uuid:pk>/<str:action>/", views.message_action, name="message_action"),
]
