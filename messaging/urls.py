from django.urls import path

from . import views


urlpatterns = [

    path("", views.inbox, name="inbox"),

    path("people/", views.people, name="people"),
    path("people/<int:user_id>/message/", views.start_dm, name="start_dm"),

    path("groups/", views.groups, name="groups"),
    path("groups/new/", views.new_conversation, name="new_conversation"),
    path("groups/<int:conversation_id>/join/", views.join_group, name="join_group"),
    path("groups/<int:conversation_id>/leave/", views.leave_group, name="leave_group"),

    path("people/<int:user_id>/block/", views.block_user, name="block_user"),
    path("people/<int:user_id>/unblock/", views.unblock_user, name="unblock_user"),
    path("blocked/", views.blocked_list, name="blocked"),

    path("profile/", views.profile_view, name="profile"),

    path("ably-auth/", views.ably_auth, name="ably_auth"),

    path("messages/<int:message_id>/report/", views.report_message, name="report_message"),
    path("messages/<int:message_id>/react/", views.react_to_message, name="react_to_message"),

    path("chat/<int:conversation_id>/", views.conversation_view, name="conversation"),
    path(
        "chat/<int:conversation_id>/send/",
        views.send_message,
        name="send_message"
    ),
    path(
        "chat/<int:conversation_id>/since/<int:last_id>/",
        views.messages_since,
        name="messages_since"
    ),

]
