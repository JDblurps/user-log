from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):

    title = models.CharField(
        max_length=120,
        blank=True
    )

    is_group = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_conversations"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def display_name_for(self, user):

        if self.is_group:
            return self.title or "Group chat"

        other = (
            self.members
            .exclude(user=user)
            .select_related("user")
            .first()
        )

        return other.user.username if other else "Direct chat"

    def __str__(self):

        return self.title or f"Conversation {self.pk}"


class Membership(models.Model):

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_memberships"
    )

    joined_at = models.DateTimeField(
        auto_now_add=True
    )

    last_read_at = models.DateTimeField(
        default=timezone.now
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_member"
            )
        ]


class Message(models.Model):

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    body = models.TextField(max_length=4000)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = ["created_at"]

    def __str__(self):

        return f"{self.sender.username}: {self.body[:40]}"
