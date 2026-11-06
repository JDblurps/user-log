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

    path("chat/<int:conversation_id>/", views.conversation_view, name="conversation"),
    path(
        "chat/<int:conversation_id>/since/<int:last_id>/",
        views.messages_since,
        name="messages_since"
    ),

]
