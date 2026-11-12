"""Ably helpers: sign browser tokens and publish messages.

The API key (settings.ABLY_API_KEY) stays on the server. Browsers only ever
receive short-lived tokens that allow them to *subscribe* to one room.
"""

import base64
import hashlib
import hmac
import json
import time
from urllib.request import Request, urlopen

from django.conf import settings


TOKEN_TTL_SECONDS = 3600


def enabled():

    return bool(getattr(settings, "ABLY_API_KEY", ""))


def channel_name(conversation_id):

    return f"chat-{conversation_id}"


def typing_channel_name(conversation_id):

    return f"typing-{conversation_id}"


def _b64url(data):

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_subscribe_token(user_id, conversation_id):
    """An Ably JWT that can only subscribe to this one room."""

    key = getattr(settings, "ABLY_API_KEY", "")

    if ":" not in key:
        return None

    key_name, secret = key.split(":", 1)

    now = int(time.time())

    header = {"typ": "JWT", "alg": "HS256", "kid": key_name}

    claims = {
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        # Chat channel: listen + show who's online. Only our server can
        # publish there. Typing channel: everyone in the room may publish.
        "x-ably-capability": json.dumps({
            channel_name(conversation_id): ["subscribe", "presence"],
            typing_channel_name(conversation_id): ["subscribe", "publish"],
        }),
        "x-ably-clientId": str(user_id),
    }

    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(claims, separators=(",", ":")).encode())
    )

    signature = hmac.new(
        secret.encode(),
        signing_input.encode(),
        hashlib.sha256
    ).digest()

    return signing_input + "." + _b64url(signature)


def publish(conversation_id, payload, event="message"):
    """Publish a message to the room. Returns True on success."""

    key = getattr(settings, "ABLY_API_KEY", "")

    if not key:
        return False

    body = json.dumps({
        "name": event,
        "data": json.dumps(payload),
    }).encode()

    auth = base64.b64encode(key.encode()).decode()

    request = Request(
        # clientType=server declares this call as coming from our server,
        # which Ably's MAU pricing requires (and doesn't count as a user).
        f"https://rest.ably.io/channels/{channel_name(conversation_id)}"
        "/messages?clientType=server",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=4) as response:
            response.read()
        return True
    except Exception:
        return False
