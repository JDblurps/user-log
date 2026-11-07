from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from messaging.models import Membership
from messaging.utils import get_general_room


class Command(BaseCommand):

    help = (
        "Create the General room (if missing) and add every active user "
        "to it. Safe to run more than once."
    )

    def handle(self, *args, **options):

        room = get_general_room()

        existing = set(
            Membership.objects
            .filter(conversation=room)
            .values_list("user_id", flat=True)
        )

        User = get_user_model()

        new = [
            Membership(conversation=room, user_id=user_id)
            for user_id in User.objects
            .filter(is_active=True)
            .values_list("id", flat=True)
            if user_id not in existing
        ]

        Membership.objects.bulk_create(new)

        self.stdout.write(
            self.style.SUCCESS(
                f"General room ready. Added {len(new)} user(s)."
            )
        )
