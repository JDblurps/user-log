import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Membership


class ChatConsumer(AsyncWebsocketConsumer):
    """Receive-only. Messages are sent over HTTP (see views.send_message),
    where block checks and rate limits are enforced, then broadcast here."""

    async def connect(self):

        self.conversation_id = (
            self.scope["url_route"]["kwargs"]["conversation_id"]
        )

        self.room_group_name = f"chat_{self.conversation_id}"

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

        # Anything sent over the socket is ignored on purpose.
        return


    async def chat_message(self, event):

        await self.send(text_data=json.dumps(event))


    @database_sync_to_async
    def is_member(self, user_id):

        return Membership.objects.filter(
            conversation_id=self.conversation_id,
            user_id=user_id
        ).exists()
