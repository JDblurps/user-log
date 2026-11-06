from django.contrib import admin

from .models import (
    Conversation,
    Membership,
    Message
)

admin.site.register(Conversation)
admin.site.register(Membership)
admin.site.register(Message)
