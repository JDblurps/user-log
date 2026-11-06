from django import forms

from .models import Conversation, Membership


class GroupForm(forms.Form):

    title = forms.CharField(
        max_length=120,

        widget=forms.TextInput(
            attrs={
                "class": "field",
                "placeholder": "Group name"
            }
        ),

        help_text="Groups are open: anyone on the site can find and join them."
    )

    def __init__(self, *args, user=None, **kwargs):

        super().__init__(*args, **kwargs)

        self.user = user

    def save(self):

        conversation = Conversation.objects.create(
            title=self.cleaned_data["title"].strip(),
            is_group=True,
            created_by=self.user
        )

        Membership.objects.create(
            conversation=conversation,
            user=self.user
        )

        return conversation
