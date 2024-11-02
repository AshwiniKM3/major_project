from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/queue/(?P<user_id>[^/]+)/$', consumers.QueueConsumer.as_asgi()),
]
