import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.models import Q

from .models import Block, Conversation, Membership


def client_ip(request):

    real = request.META.get("HTTP_X_REAL_IP", "").strip()

    if real:
        return real[:64]

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")

    if forwarded:
        return forwarded.split(",")[0].strip()[:64]

    return request.META.get("REMOTE_ADDR", "")[:64]


def verify_turnstile(request):
    """Cloudflare Turnstile check. Skipped when no secret key is configured."""

    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")

    if not secret:
        return True

    token = request.POST.get("cf-turnstile-response", "")

    if not token:
        return False

    data = urlencode({
        "secret": secret,
        "response": token,
        "remoteip": client_ip(request),
    }).encode()

    try:
        with urlopen(
            Request(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=data
            ),
            timeout=5
        ) as response:
            return json.load(response).get("success") is True
    except Exception:
        return False


def blocked_ids_for(user):
    """IDs of people `user` has blocked."""

    return set(
        Block.objects
        .filter(blocker=user)
        .values_list("blocked_id", flat=True)
    )


def is_blocked_between(a_id, b_id):
    """True if either person has blocked the other."""

    return Block.objects.filter(
        Q(blocker_id=a_id, blocked_id=b_id)
        | Q(blocker_id=b_id, blocked_id=a_id)
    ).exists()


def get_general_room():

    room = Conversation.objects.filter(is_default=True).first()

    if room is None:
        room = Conversation.objects.create(
            title="General",
            is_group=True,
            is_default=True
        )

    return room


def join_default_rooms(user):

    Membership.objects.get_or_create(
        conversation=get_general_room(),
        user=user
    )
