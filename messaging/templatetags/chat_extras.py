import re

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from messaging.avatars import avatar_info


register = template.Library()


@register.simple_tag
def avatar(user, size=42):
    """A round avatar: the user's emoji, or their initial, on their color."""

    info = avatar_info(user)

    size = int(size)

    return format_html(
        '<div class="avatar" style="background:{};color:#fff;'
        'width:{}px;height:{}px;font-size:{}px">{}</div>',
        info["color"],
        size,
        size,
        max(10, round(size * 0.5)),
        info["emoji"] or info["initial"],
    )


MENTION = re.compile(r"@(\w{1,150})")


@register.filter
def chat_body(value, me=""):
    """Escape a message, keep line breaks, and highlight @mentions
    (yours get an extra highlight)."""

    text = str(escape(value))

    me = str(me).lower()

    def wrap(match):

        name = match.group(1)

        css = "mention me" if name.lower() == me else "mention"

        return f'<span class="{css}">@{name}</span>'

    text = MENTION.sub(wrap, text)

    text = text.replace("\r\n", "\n").replace("\n", "<br>")

    return mark_safe(text)
