import json
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import GroupForm
from .models import Conversation, Membership, Message


User = get_user_model()

HISTORY_LIMIT = 200
LIST_LIMIT = 100


def register_view(request):

    if request.user.is_authenticated:
        return redirect("inbox")

    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        user = form.save()
        login(request, user)

        return redirect("inbox")

    return render(request, "registration/register.html", {"form": form})


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

        chats.append({
            "conversation": conversation,
            "name": conversation.display_name_for(request.user),
            "latest": latest,
            "unread": unread
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

    recent = list(
        conversation.messages
        .select_related("sender")
        .order_by("-created_at")[:HISTORY_LIMIT]
    )

    recent.reverse()

    return render(
        request,
        "messaging/conversation.html",
        {
            "conversation": conversation,
            "conversation_name": conversation.display_name_for(request.user),
            "chat_messages": recent
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
        .select_related("sender")
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

    try:
        data = json.loads(request.body)
        body = str(data.get("body", "")).strip()
    except (ValueError, AttributeError):
        return JsonResponse({"error": "bad request"}, status=400)

    if not body or len(body) > 4000:
        return JsonResponse({"error": "invalid message"}, status=400)

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
    }

    try:
        layer = get_channel_layer()

        async_to_sync(layer.group_send)(
            f"chat_{conversation_id}",
            {"type": "chat_message", **payload}
        )
    except Exception:
        # The message is saved; other viewers will catch up on reconnect.
        pass

    return JsonResponse(payload)