from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket URL'sinden ev ID'sini yakalayacak Regex
    re_path(r'^ws/alerts/(?P<home_id>\w+)/$', consumers.AlertConsumer.as_asgi()),
]