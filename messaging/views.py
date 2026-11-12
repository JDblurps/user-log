import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import GroupForm
from .models import (
    Block,
    Conversation,
    Membership,
    Message,
    Profile,
    Reaction,
    Report,
    SignupAttempt,
)
from . import realtime
from .avatars import AVATARS, COLORS, avatar_info, avatar_payload
from .features import REACTIONS, apply_command
from .utils import (
    blocked_ids_for,
    client_ip,
    is_blocked_between,
    join_default_rooms,
    verify_turnstile,
)


User = get_user_model()

HISTORY_LIMIT = 200
LIST_LIMIT = 100


SIGNUPS_PER_IP_PER_HOUR = 5


def register_view(request):

    if request.user.is_authenticated:
        return redirect("inbox")

    form = UserCreationForm(request.POST or None)

    if request.method == "POST":

        ip = client_ip(request)

        too_many = SignupAttempt.objects.filter(
            ip=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count() >= SIGNUPS_PER_IP_PER_HOUR

        if too_many:

            messages.error(
                request,
                "Too many accounts were created from your network. "
                "Please try again later."
            )

        elif not verify_turnstile(request):

            messages.error(
                request,
                "Please complete the verification and try again."
            )

        elif form.is_valid():

            user = form.save()

            SignupAttempt.objects.create(ip=ip)

            join_default_rooms(user)

            login(request, user)

            return redirect("inbox")

    return render(
        request,
        "registration/register.html",
        {
            "form": form,
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        }
    )


@login_required
def inbox(request):

    memberships = (
        Membership.objects
        .filter(user=request.user)
        .select_related("conversation")
        .order_by("-conversation__created_at")
    )

    chats = []

    for membership in memberships:

        conversation = membership.conversation

        latest = (
            conversation.messages
            .select_related("sender")
            .last()
        )

        unread = (
            conversation.messages
            .filter(created_at__gt=membership.last_read_at)
            .exclude(sender=request.user)
            .count()
        )

        other_user = None

        if not conversation.is_group:

            other = (
                conversation.members
                .exclude(user=request.user)
                .select_related("user__profile")
                .first()
            )

            other_user = other.user if other else None

        chats.append({
            "conversation": conversation,
            "name": conversation.display_name_for(request.user),
            "latest": latest,
            "unread": unread,
            "other_user": other_user,
        })

    return render(request, "messaging/inbox.html", {"chats": chats})


# ---------- People directory + direct messages ----------

@login_required
def people(request):

    q = request.GET.get("q", "").strip()

    users = (
        User.objects
        .filter(is_active=True)
        .exclude(pk=request.user.pk)
        .select_related("profile")
    )

    if q:
        users = users.filter(username__icontains=q)

    users = users.order_by("username")[:LIST_LIMIT]

    return render(
        request,
        "messaging/people.html",
        {"people": users, "q": q}
    )


@login_required
@require_POST
def start_dm(request, user_id):

    other = get_object_or_404(User, pk=user_id, is_active=True)

    if other.pk == request.user.pk:
        return redirect("inbox")

    if is_blocked_between(request.user.pk, other.pk):

        messages.error(request, "You can't message this person.")

        return redirect("people")

    with transaction.atomic():

        candidates = (
            Conversation.objects
            .filter(is_group=False, members__user=request.user)
            .filter(members__user=other)
            .distinct()
        )

        conversation = None

        for candidate in candidates:
            if candidate.members.count() == 2:
                conversation = candidate
                break

        if conversation is None:

            conversation = Conversation.objects.create(
                is_group=False,
                created_by=request.user
            )

            Membership.objects.create(
                conversation=conversation,
                user=request.user
            )

            Membership.objects.create(
                conversation=conversation,
                user=other
            )

    return redirect("conversation", conversation_id=conversation.pk)


# ---------- Open groups ----------

@login_required
def groups(request):

    q = request.GET.get("q", "").strip()

    qs = (
        Conversation.objects
        .filter(is_group=True)
        .annotate(member_count=Count("members"))
    )

    if q:
        qs = qs.filter(title__icontains=q)

    qs = qs.order_by("-member_count", "title")[:LIST_LIMIT]

    my_ids = set(
        Membership.objects
        .filter(user=request.user)
        .values_list("conversation_id", flat=True)
    )

    return render(
        request,
        "messaging/groups.html",
        {"groups": qs, "my_ids": my_ids, "q": q}
    )


@login_required
def new_conversation(request):
    """Create a new (open) group."""

    form = GroupForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():

        conversation = form.save()

        return redirect("conversation", conversation_id=conversation.pk)

    return render(
        request,
        "messaging/new_conversation.html",
        {"form": form}
    )


@login_required
@require_POST
def join_group(request, conversation_id):

    conversation = get_object_or_404(
        Conversation,
        pk=conversation_id,
        is_group=True
    )

    Membership.objects.get_or_create(
        conversation=conversation,
        user=request.user
    )

    return redirect("conversation", conversation_id=conversation.pk)


@login_required
@require_POST
def leave_group(request, conversation_id):

    Membership.objects.filter(
        conversation_id=conversation_id,
        conversation__is_group=True,
        user=request.user
    ).delete()

    return redirect("inbox")


# ---------- Conversation ----------

@login_required
def conversation_view(request, conversation_id):

    conversation = get_object_or_404(
        Conversation,
        pk=conversation_id,
        members__user=request.user
    )

    membership = get_object_or_404(
        Membership,
        conversation=conversation,
        user=request.user
    )

    if request.method == "POST":

        body = request.POST.get("body", "").strip()

        if body and len(body) <= 4000:

            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                body=body
            )

        return redirect("conversation", conversation_id=conversation.pk)

    membership.last_read_at = timezone.now()
    membership.save(update_fields=["last_read_at"])

    blocked = blocked_ids_for(request.user)

    recent = list(
        conversation.messages
        .select_related("sender__profile")
        .exclude(sender_id__in=blocked)
        .order_by("-created_at")[:HISTORY_LIMIT]
    )

    recent.reverse()

    # Reactions for the messages on screen: {message_id: {emoji: [user_ids]}}
    reaction_data = {}

    reaction_rows = Reaction.objects.filter(
        message_id__in=[m.id for m in recent]
    ).values_list("message_id", "emoji", "user_id")

    for message_id, emoji, user_id in reaction_rows:
        reaction_data.setdefault(message_id, {}).setdefault(emoji, []).append(user_id)

    return render(
        request,
        "messaging/conversation.html",
        {
            "conversation": conversation,
            "conversation_name": conversation.display_name_for(request.user),
            "chat_messages": recent,
            "blocked_ids": sorted(blocked),
            "realtime": realtime.enabled(),
            "reaction_data": reaction_data,
            "reaction_emoji": REACTIONS,
        }
    )


@login_required
def messages_since(request, conversation_id, last_id):
    """Messages newer than last_id. Used by the browser to catch up
    after the WebSocket reconnects."""

    get_object_or_404(
        Membership,
        conversation_id=conversation_id,
        user=request.user
    )

    msgs = (
        Message.objects
        .filter(conversation_id=conversation_id, id__gt=last_id)
        .exclude(sender_id__in=blocked_ids_for(request.user))
        .select_related("sender__profile")
        .order_by("id")[:HISTORY_LIMIT]
    )

    return JsonResponse({
        "messages": [
            {
                "id": m.id,
                "body": m.body,
                "sender": m.sender.username,
                "sender_id": m.sender_id,
                "created_at": m.created_at.isoformat(),
                **avatar_payload(m.sender),
            }
            for m in msgs
        ]
    })


@login_required
@require_POST
def send_message(request, conversation_id):
    """Save a message and broadcast it to the room.

    The browser sends messages here over plain HTTP so a send never
    silently disappears if the WebSocket happens to be reconnecting.
    The WebSocket is only used to receive.
    """

    get_object_or_404(
        Membership,
        conversation_id=conversation_id,
        user=request.user
    )

    conversation = get_object_or_404(Conversation, pk=conversation_id)

    if not conversation.is_group:

        other = (
            Membership.objects
            .filter(conversation=conversation)
            .exclude(user=request.user)
            .first()
        )

        if other and is_blocked_between(request.user.pk, other.user_id):
            return JsonResponse({"error": "blocked"}, status=403)

    try:
        data = json.loads(request.body)
        body = str(data.get("body", "")).strip()
    except (ValueError, AttributeError):
        return JsonResponse({"error": "bad request"}, status=400)

    if not body or len(body) > 4000:
        return JsonResponse({"error": "invalid message"}, status=400)

    # Slash commands (/roll, /flip, /8ball, /choose, /me, /shrug).
    body = apply_command(request.user.username, body)[:4000]

    # Basic flood protection: one message per half second per user.
    too_fast = Message.objects.filter(
        sender=request.user,
        created_at__gte=timezone.now() - timedelta(milliseconds=500)
    ).exists()

    if too_fast:
        return JsonResponse({"error": "slow down"}, status=429)

    message = Message.objects.create(
        conversation_id=conversation_id,
        sender=request.user,
        body=body
    )

    payload = {
        "id": message.id,
        "body": message.body,
        "sender": request.user.username,
        "sender_id": request.user.id,
        "created_at": message.created_at.isoformat(),
        **avatar_payload(request.user),
    }

    # Push to everyone in the room. If this fails the message is still
    # saved, and other browsers pick it up on their next catch-up.
    realtime.publish(conversation_id, payload)

    return JsonResponse(payload)


# ---------- Blocking and reporting ----------

@login_required
@require_POST
def block_user(request, user_id):

    target = get_object_or_404(User, pk=user_id)

    if target.pk != request.user.pk:

        Block.objects.get_or_create(
            blocker=request.user,
            blocked=target
        )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def unblock_user(request, user_id):

    Block.objects.filter(
        blocker=request.user,
        blocked_id=user_id
    ).delete()

    return redirect("blocked")


@login_required
def blocked_list(request):

    blocks = (
        Block.objects
        .filter(blocker=request.user)
        .select_related("blocked__profile")
        .order_by("blocked__username")
    )

    return render(
        request,
        "messaging/blocked.html",
        {"blocks": blocks}
    )


REPORTS_PER_HOUR = 20


@login_required
@require_POST
def report_message(request, message_id):

    message = get_object_or_404(
        Message.objects.select_related("sender"),
        pk=message_id
    )

    # You can only report messages from rooms you are in.
    get_object_or_404(
        Membership,
        conversation_id=message.conversation_id,
        user=request.user
    )

    if message.sender_id == request.user.id:
        return JsonResponse({"error": "invalid"}, status=400)

    recent = Report.objects.filter(
        reporter=request.user,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()

    if recent >= REPORTS_PER_HOUR:
        return JsonResponse({"error": "slow down"}, status=429)

    try:
        reason = str(json.loads(request.body).get("reason", "")).strip()[:500]
    except (ValueError, AttributeError):
        reason = ""

    Report.objects.get_or_create(
        reporter=request.user,
        message=message,
        defaults={
            "reported_user": message.sender,
            "message_body": message.body,
            "reason": reason,
        }
    )

    return JsonResponse({"ok": True})


@login_required
def ably_auth(request):
    """Gives the browser a short-lived token to subscribe to one room."""

    conversation_id = request.GET.get("conversation", "")

    if not conversation_id.isdigit():
        return HttpResponse(status=400)

    get_object_or_404(
        Membership,
        conversation_id=int(conversation_id),
        user=request.user
    )

    token = realtime.make_subscribe_token(
        request.user.pk,
        int(conversation_id)
    )

    if not token:
        return HttpResponse(status=503)

    return HttpResponse(token, content_type="text/plain")


# ---------- Profile customization ----------

@login_required
def profile_view(request):

    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":

        color = request.POST.get("color", "")
        avatar = request.POST.get("avatar", "")

        if color in COLORS and (avatar == "" or avatar in AVATARS):

            profile.color = color
            profile.avatar = avatar
            profile.save()

            messages.success(request, "Profile updated.")

            return redirect("profile")

        messages.error(request, "Please pick a color and an avatar from the lists.")

    current = avatar_info(request.user)

    return render(
        request,
        "messaging/profile.html",
        {
            "colors": COLORS,
            "avatars": AVATARS,
            "selected_color": profile.color or current["color"],
            "selected_avatar": profile.avatar,
        }
    )


# ---------- Reactions ----------

def reaction_state(message):
    """{emoji: [user_ids]} for one message."""

    state = {}

    for emoji, user_id in Reaction.objects.filter(
        message=message
    ).values_list("emoji", "user_id"):
        state.setdefault(emoji, []).append(user_id)

    return state


@login_required
@require_POST
def react_to_message(request, message_id):
    """Toggle your reaction on a message and tell everyone in the room."""

    message = get_object_or_404(Message, pk=message_id)

    get_object_or_404(
        Membership,
        conversation_id=message.conversation_id,
        user=request.user
    )

    try:
        emoji = str(json.loads(request.body).get("emoji", ""))
    except (ValueError, AttributeError):
        emoji = ""

    if emoji not in REACTIONS:
        return JsonResponse({"error": "invalid"}, status=400)

    existing = Reaction.objects.filter(
        message=message,
        user=request.user,
        emoji=emoji
    )

    if existing.exists():

        existing.delete()

    else:

        recent = Reaction.objects.filter(
            user=request.user,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()

        if recent >= 30:
            return JsonResponse({"error": "slow down"}, status=429)

        Reaction.objects.create(
            message=message,
            user=request.user,
            emoji=emoji
        )

    payload = {
        "message_id": message.id,
        "reactions": reaction_state(message),
    }

    realtime.publish(message.conversation_id, payload, event="reaction")

    return JsonResponse(payload)
