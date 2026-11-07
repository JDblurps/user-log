from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import (
    Block,
    Conversation,
    Membership,
    Message,
    Report,
    SignupAttempt,
)


User = get_user_model()


# ---- Users: ban / unban ----

admin.site.unregister(User)


@admin.register(User)
class ChatUserAdmin(UserAdmin):

    list_display = (
        "username", "is_active", "is_staff", "date_joined", "last_login"
    )

    list_filter = ("is_active", "is_staff")

    actions = ["ban_users", "unban_users"]

    @admin.action(description="Ban selected users (they can no longer log in)")
    def ban_users(self, request, queryset):

        count = queryset.exclude(is_superuser=True).update(is_active=False)

        self.message_user(request, f"{count} user(s) banned.")

    @admin.action(description="Unban selected users")
    def unban_users(self, request, queryset):

        count = queryset.update(is_active=True)

        self.message_user(request, f"{count} user(s) unbanned.")


# ---- Reports ----

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):

    list_display = (
        "id", "status", "reporter", "reported_user",
        "short_body", "reason", "created_at"
    )

    list_filter = ("status",)

    search_fields = (
        "reporter__username", "reported_user__username",
        "message_body", "reason"
    )

    actions = [
        "mark_resolved",
        "ban_reported_users",
        "delete_reported_messages",
    ]

    @admin.display(description="Message")
    def short_body(self, obj):

        return obj.message_body[:60]

    @admin.action(description="Mark selected reports as resolved")
    def mark_resolved(self, request, queryset):

        count = queryset.update(status=Report.STATUS_RESOLVED)

        self.message_user(request, f"{count} report(s) resolved.")

    @admin.action(description="Ban the reported users and resolve")
    def ban_reported_users(self, request, queryset):

        user_ids = list(
            queryset
            .exclude(reported_user__isnull=True)
            .values_list("reported_user_id", flat=True)
        )

        banned = (
            User.objects
            .filter(pk__in=user_ids)
            .exclude(is_superuser=True)
            .update(is_active=False)
        )

        queryset.update(status=Report.STATUS_RESOLVED)

        self.message_user(request, f"{banned} user(s) banned.")

    @admin.action(description="Delete the reported messages and resolve")
    def delete_reported_messages(self, request, queryset):

        message_ids = list(
            queryset
            .exclude(message__isnull=True)
            .values_list("message_id", flat=True)
        )

        Message.objects.filter(pk__in=message_ids).delete()

        queryset.update(status=Report.STATUS_RESOLVED)

        self.message_user(request, "Reported messages deleted.")


# ---- Everything else ----

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):

    list_display = ("id", "sender", "conversation", "short_body", "created_at")

    search_fields = ("body", "sender__username")

    @admin.display(description="Body")
    def short_body(self, obj):

        return obj.body[:60]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):

    list_display = ("id", "title", "is_group", "is_default", "created_at")


admin.site.register(Membership)
admin.site.register(Block)
admin.site.register(SignupAttempt)
