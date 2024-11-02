# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
import redis

redis_instance = redis.StrictRedis(host='localhost', port=6379, db=0)

class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.group_name = f'queue_{self.user_id}'

        # Join the room group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the room group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def send_queue_update(self, event):
        # Retrieve user data from Redis
        user_data = redis_instance.hgetall(self.user_id)
        user_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()}

        # Send the data to the WebSocket
        await self.send(text_data=json.dumps({
            'status': user_data.get('status', 'unknown'),
            'people_ahead': user_data.get('people_ahead', 'unknown')
        }))
