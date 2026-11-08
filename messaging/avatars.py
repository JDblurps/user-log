"""Preset colors and avatars, plus helpers to describe a user's look."""

COLORS = [
    "#4f46e5", "#7c3aed", "#c026d3", "#db2777",
    "#dc2626", "#ea580c", "#d97706", "#65a30d",
    "#16a34a", "#0d9488", "#0891b2", "#2563eb",
]

AVATARS = [
    "😀", "😎", "🤓", "🥳", "😺", "🐶",
    "🦊", "🐼", "🐸", "🦄", "🐙", "🦁",
    "🐧", "🦉", "🌵", "🌈", "🔥", "⚡",
    "🚀", "👾", "🎮", "🎧", "🍕", "🍩",
]


def avatar_info(user):
    """Color, emoji (or '') and initial for a user. Never raises, and works
    for users who never customized anything."""

    profile = getattr(user, "profile", None)

    color = profile.color if profile and profile.color else ""

    if color not in COLORS:
        color = COLORS[user.pk % len(COLORS)]

    emoji = profile.avatar if profile and profile.avatar in AVATARS else ""

    initial = (user.username[:1] or "?").upper()

    return {"color": color, "emoji": emoji, "initial": initial}


def avatar_payload(user):
    """The same info, shaped for the JSON that goes to browsers."""

    info = avatar_info(user)

    return {
        "sender_color": info["color"],
        "sender_avatar": info["emoji"],
        "sender_initial": info["initial"],
    }
