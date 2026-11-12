from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):

    title = models.CharField(
        max_length=120,
        blank=True
    )

    is_group = models.BooleanField(default=False)

    # The group every new user is added to automatically (the "General" room).
    is_default = models.BooleanField(default=False)

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


class Block(models.Model):
    """`blocker` doesn't want to see or hear from `blocked`."""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_made"
    )

    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_block"
            )
        ]

    def __str__(self):

        return f"{self.blocker} blocked {self.blocked}"


class Report(models.Model):

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_made"
    )

    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_received"
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports"
    )

    # Snapshot, so the evidence survives if the message is deleted.
    message_body = models.TextField(blank=True)

    reason = models.CharField(max_length=500, blank=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["-created_at"]

    def __str__(self):

        return f"Report #{self.pk} ({self.status})"


class SignupAttempt(models.Model):
    """One row per successful signup, used to limit signups per IP."""

    ip = models.CharField(max_length=64, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Profile(models.Model):
    """Optional look customization. Users without one get defaults."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    # One of messaging.avatars.COLORS (empty = automatic color).
    color = models.CharField(max_length=7, blank=True)

    # One of messaging.avatars.AVATARS (empty = use the initial).
    avatar = models.CharField(max_length=16, blank=True)

    def __str__(self):

        return f"Profile of {self.user}"


class Reaction(models.Model):
    """One emoji reaction by one user on one message."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reactions"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions"
    )

    emoji = models.CharField(max_length=8)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"],
                name="unique_reaction"
            )
        ]

    def __str__(self):

        return f"{self.user} {self.emoji} on message {self.message_id}"
