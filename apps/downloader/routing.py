"""WebSocket URL routing."""
from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/downloads/<uuid:download_id>/", consumers.DownloadProgressConsumer.as_asgi()),
    path("ws/user/", consumers.UserEventsConsumer.as_asgi()),
]
