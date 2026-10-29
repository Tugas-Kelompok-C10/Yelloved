from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import MessageEditForm, MessageForm
from .models import Conversation, Message


def _pair(user, peer):
    first, second = sorted((user.pk, peer.pk))
    return {"first_user_id": first, "second_user_id": second}


def _peer(request, user_id):
    return get_object_or_404(get_user_model().objects.filter(is_active=True).exclude(pk=request.user.pk), pk=user_id)


def _conversation_list(user):
    latest = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at", "-pk")
    rows = Conversation.objects.filter(Q(first_user=user) | Q(second_user=user)).select_related("first_user", "second_user").annotate(
        recent_body=Subquery(latest.values("body")[:1]),
        recent_at=Coalesce(Subquery(latest.values("created_at")[:1]), "created_at"),
    ).order_by("-recent_at", "pk")
    return [{"peer": row.second_user if row.first_user_id == user.pk else row.first_user,
             "preview": row.recent_body or "Message deleted."} for row in rows[:50]]


def _render(request, peer=None):
    return render(request, "chat/inbox.html", {"name": "Yelloved", "peer": peer,
        "conversations": _conversation_list(request.user)})


def _entry(message, user):
    return {"id": str(message.pk), "body": message.body if not message.deleted_at else "",
        "mine": message.sender_id == user.pk, "deleted": bool(message.deleted_at),
        "created_at": message.created_at.isoformat(), "revision": message.edited_at.isoformat(),
        "edit_url": reverse("chat:message_action", args=[message.pk, "edit"]),
        "delete_url": reverse("chat:message_action", args=[message.pk, "delete"])}


def _error(message, status=400):
    return JsonResponse({"message": message}, status=status)


@login_required
def inbox(request):
    return _render(request)


@login_required
def with_user(request, user_id):
    return _render(request, _peer(request, user_id))


@require_GET
def inbox_api(request):
    if not request.user.is_authenticated:
        return _error("Your session has expired. Please sign in again.", 401)
    return JsonResponse({"conversations": [{"peer_id": row["peer"].pk,
        "name": row["peer"].get_full_name() or row["peer"].username,
        "preview": row["preview"][:80], "url": reverse("chat:with_user", args=[row["peer"].pk])}
        for row in _conversation_list(request.user)]})


@require_http_methods(["GET", "POST"])
def messages_api(request, user_id):
    if not request.user.is_authenticated:
        return _error("Your session has expired. Please sign in again.", 401)
    peer = get_user_model().objects.filter(pk=user_id, is_active=True).exclude(pk=request.user.pk).first()
    if not peer:
        return _error("This user is unavailable. You cannot chat with yourself.", 404)
    pair = _pair(request.user, peer)
    if request.method == "GET":
        conversation = Conversation.objects.filter(**pair).first()
        entries = Message.objects.filter(conversation=conversation) if conversation else Message.objects.none()
        # Fetch the newest 50, then allow older history without loading everything.
        before = request.GET.get("before")
        if before:
            cursor = entries.filter(pk=before).first() if _valid_uuid(before) else None
            if not cursor:
                return _error("That message page is no longer available. Refresh the chat.", 400)
            entries = entries.filter(Q(created_at__lt=cursor.created_at) | Q(created_at=cursor.created_at, pk__lt=cursor.pk))
        batch = list(entries.order_by("-created_at", "-pk")[:51])
        has_older = len(batch) > 50
        batch = list(reversed(batch[:50]))
        return JsonResponse({"messages": [_entry(entry, request.user) for entry in batch], "has_older": has_older})

    form = MessageForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"message": "Enter a message of 1–1000 characters.", "errors": form.errors.get_json_data()}, status=422)
    with transaction.atomic():
        conversation, _ = Conversation.objects.get_or_create(**pair)
        message, created = Message.objects.get_or_create(pk=form.cleaned_data["client_id"], defaults={
            "conversation": conversation, "sender": request.user, "body": form.cleaned_data["body"]})
        if message.sender_id != request.user.pk or message.conversation_id != conversation.pk:
            transaction.set_rollback(True)
            return _error("This send token belongs to a different message. Please compose a new message.", 409)
    return JsonResponse({"entry": _entry(message, request.user)}, status=201 if created else 200)


def _valid_uuid(value):
    from uuid import UUID
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@require_POST
def message_action(request, pk, action):
    if not request.user.is_authenticated:
        return _error("Your session has expired. Please sign in again.", 401)
    message = Message.objects.filter(pk=pk, sender=request.user).first()
    if not message:
        return _error("This message is unavailable or you do not have permission to change it.", 404)
    if action not in ("edit", "delete"):
        return _error("Unknown message action.", 404)
    if action == "edit":
        form = MessageEditForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"message": "Enter a message of 1–1000 characters and reload if its version is outdated.",
                                 "errors": form.errors.get_json_data()}, status=422)
        revision = form.cleaned_data["revision"]
    else:
        try:
            revision = parse_datetime(request.POST.get("revision", ""))
        except ValueError:
            revision = None
        if not revision or timezone.is_naive(revision):
            return _error("Refresh the conversation before deleting this message.", 422)
    now = timezone.now()
    changes = {"edited_at": now, "body": form.cleaned_data["body"]} if action == "edit" else {"edited_at": now, "deleted_at": now, "body": ""}
    changed = Message.objects.filter(pk=pk, sender=request.user, edited_at=revision, deleted_at__isnull=True).update(**changes)
    if not changed:
        return _error("This message changed in another tab or was deleted. Refresh the chat before trying again.", 409)
    message.refresh_from_db()
    return JsonResponse({"message": "Message updated." if action == "edit" else "Message deleted.", "entry": _entry(message, request.user)})
