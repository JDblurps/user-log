import json
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Membership, Message


# Basic flood protection: at most ~2 messages per second per connection.
MIN_SECONDS_BETWEEN_MESSAGES = 0.5


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.conversation_id = (
            self.scope["url_route"]["kwargs"]["conversation_id"]
        )

        self.room_group_name = f"chat_{self.conversation_id}"

        self.last_sent = 0.0

        user = self.scope["user"]

        if (
            not user.is_authenticated
            or not await self.is_member(user.id)
        ):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()


    async def disconnect(self, close_code):

        if hasattr(self, "room_group_name"):

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )


    async def receive(self, text_data=None, bytes_data=None):

        try:
            data = json.loads(text_data)
            body = str(data.get("body", "")).strip()
        except (json.JSONDecodeError, AttributeError, TypeError):
            return

        if not body or len(body) > 4000:
            return

        now = time.monotonic()

        if now - self.last_sent < MIN_SECONDS_BETWEEN_MESSAGES:
            return

        self.last_sent = now

        user = self.scope["user"]

        message = await self.save_message(user.id, body)

        if message:

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "id": message["id"],
                    "body": message["body"],
                    "sender": message["sender"],
                    "sender_id": message["sender_id"],
                    "created_at": message["created_at"],
                }
            )


    async def chat_message(self, event):

        await self.send(text_data=json.dumps(event))


    @database_sync_to_async
    def is_member(self, user_id):

        return Membership.objects.filter(
            conversation_id=self.conversation_id,
            user_id=user_id
        ).exists()


    @database_sync_to_async
    def save_message(self, user_id, body):

        if not Membership.objects.filter(
            conversation_id=self.conversation_id,
            user_id=user_id
        ).exists():
            return None

        message = Message.objects.create(
            conversation_id=self.conversation_id,
            sender_id=user_id,
            body=body
        )

        return {
            "id": message.id,
            "body": message.body,
            "sender": message.sender.username,
            "sender_id": user_id,
            # ISO timestamp; the browser formats it in the viewer's timezone.
            "created_at": message.created_at.isoformat(),
        }
