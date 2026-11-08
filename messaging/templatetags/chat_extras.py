from django import template
from django.utils.html import format_html

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
