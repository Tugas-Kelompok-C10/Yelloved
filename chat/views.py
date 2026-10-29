from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import Count, F, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import MessageEditForm, MessageForm
from .models import Conversation, Message
from .session import session_guard


def _pair(user, peer):
    first, second = sorted((user.pk, peer.pk))
    return {"first_user_id": first, "second_user_id": second}


def _peer(request, user_id):
    return get_object_or_404(get_user_model().objects.filter(is_active=True).exclude(pk=request.user.pk), pk=user_id)


def _conversation_list(user, limit=50, before=None):
    latest = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at", "-pk")
    rows = Conversation.objects.filter(Q(first_user=user) | Q(second_user=user)).select_related("first_user", "second_user").annotate(
        recent_body=Subquery(latest.values("body")[:1]),
        recent_file=Subquery(latest.values("attachment_name")[:1]),
        recent_at=Coalesce(Subquery(latest.values("created_at")[:1]), "created_at"),
        unread_count=Count("messages", filter=Q(messages__read_at__isnull=True, messages__deleted_at__isnull=True) & ~Q(messages__sender=user)),
    ).order_by("-recent_at", "pk")
    if before:
        stamp, pk = before
        rows = rows.filter(Q(recent_at__lt=stamp) | Q(recent_at=stamp, pk__gt=pk))
    return [{"peer": row.second_user if row.first_user_id == user.pk else row.first_user,
             "preview": row.recent_body or (f"Attachment: {row.recent_file}" if row.recent_file else "Message deleted."),
             "unread": row.unread_count, "recent_at": row.recent_at, "id": row.pk} for row in rows[:limit]]


def _render(request, peer=None):
    return render(request, "chat/inbox.html", {"name": "Yelloved", "peer": peer,
        "conversations": _conversation_list(request.user)})


def _entry(message, user):
    return {"id": str(message.pk), "body": message.body if not message.deleted_at else "",
        "mine": message.sender_id == user.pk, "deleted": bool(message.deleted_at),
        "unread": message.sender_id != user.pk and message.read_at is None and message.deleted_at is None,
        "created_at": message.created_at.isoformat(), "revision": message.edited_at.isoformat(),
        "version": message.sync_version, "created_version": message.created_version,
        "attachment": ({"name": message.attachment_name, "url": reverse("chat:attachment", args=[message.pk])}
                       if message.attachment and not message.deleted_at else None),
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
@session_guard
def inbox_api(request):
    if not request.user.is_authenticated:
        return _error("Your session has expired. Please sign in again.", 401)
    before = None
    if request.GET.get("cursor"):
        try:
            cursor = signing.loads(request.GET["cursor"], salt="chat.inbox")
            if cursor["user"] != request.user.pk or not _valid_uuid(cursor["id"]): raise ValueError
            stamp = parse_datetime(cursor["stamp"])
            if stamp is None or timezone.is_naive(stamp): raise ValueError
            before = (stamp, cursor["id"])
        except (signing.BadSignature, ValueError, TypeError, KeyError):
            return _error("Invalid conversation page. Reload Chat.", 422)
    rows = _conversation_list(request.user, limit=51, before=before)
    more = len(rows) > 50
    rows = rows[:50]
    next_cursor = signing.dumps({"user": request.user.pk, "stamp": rows[-1]["recent_at"].isoformat(), "id": str(rows[-1]["id"])}, salt="chat.inbox") if more else None
    return JsonResponse({"conversations": [{"peer_id": row["peer"].pk,
        "name": row["peer"].get_full_name() or row["peer"].username,
        "preview": row["preview"][:80], "unread": row["unread"], "url": reverse("chat:with_user", args=[row["peer"].pk])}
        for row in rows], "next_cursor": next_cursor})


@require_GET
@session_guard
def notifications(request):
    if not request.user.is_authenticated:
        return _error("Please sign in again to check chat notifications.", 401)
    incoming = Message.objects.filter(Q(conversation__first_user=request.user) | Q(conversation__second_user=request.user),
                                     read_at__isnull=True, deleted_at__isnull=True).exclude(sender=request.user)
    return JsonResponse({"unread": incoming.count(), "conversations": [{
        "name": row["peer"].get_full_name() or row["peer"].username, "initial": row["peer"].username[:1].upper(),
        "preview": row["preview"][:100], "unread": row["unread"], "url": reverse("chat:with_user", args=[row["peer"].pk])}
        for row in _conversation_list(request.user, limit=3)]})


@require_POST
@session_guard
def mark_read(request, user_id):
    if not request.user.is_authenticated:
        return _error("Your session has expired. Please sign in again.", 401)
    ids = request.POST.getlist("ids")
    if not ids or len(ids) > 50 or not all(_valid_uuid(value) for value in ids):
        return _error("Invalid message selection.", 422)
    # Only acknowledge messages actually delivered to this participant, never
    # messages that arrived after the browser fetched the current batch.
    pair = _pair(request.user, get_object_or_404(get_user_model(), pk=user_id))
    count = Message.objects.filter(conversation__first_user_id=pair["first_user_id"],
        conversation__second_user_id=pair["second_user_id"], sender_id=user_id,
        pk__in=ids, read_at__isnull=True, deleted_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"read": count})


@require_http_methods(["GET", "POST"])
@session_guard
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
        version = conversation.sync_version if conversation else 0
        if "resolve" in request.GET:
            ids = request.GET["resolve"].split(",")
            if len(ids) > 50 or not all(_valid_uuid(value) for value in ids):
                return _error("Invalid retry message selection.", 422)
            return JsonResponse({"messages": [_entry(entry, request.user) for entry in entries.filter(pk__in=ids)]})
        if "after" in request.GET:
            try:
                after = int(request.GET["after"])
                if after < 0 or after > version: raise ValueError
            except ValueError:
                return _error("Invalid history cursor. Reload the conversation.", 422)
            batch = list(entries.filter(sync_version__gt=after).order_by("sync_version")[:101])
            more = len(batch) > 100
            batch = batch[:100]
            return JsonResponse({"messages": [_entry(entry, request.user) for entry in batch],
                "sync_cursor": batch[-1].sync_version if more else max(version, batch[-1].sync_version if batch else after),
                "has_more_changes": more})
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
        return JsonResponse({"messages": [_entry(entry, request.user) for entry in batch], "has_older": has_older, "sync_cursor": version})

    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = form.errors.get_json_data()
        detail = next((item["message"] for group in errors.values() for item in group), "Unable to send this message.")
        return JsonResponse({"message": detail, "errors": errors}, status=422)
    written = None
    try:
        with transaction.atomic():
            conversation, _ = Conversation.objects.get_or_create(**pair)
            # Serialize writers before allocating a change version. A cursor can
            # only advance past writes that have committed for this conversation.
            Conversation.objects.filter(pk=conversation.pk).update(sync_version=F("sync_version") + 1)
            conversation.refresh_from_db(fields=["sync_version"])
            message, created = Message.objects.get_or_create(pk=form.cleaned_data["client_id"], defaults={
                "conversation": conversation, "sender": request.user, "body": form.cleaned_data["body"],
                "sync_version": conversation.sync_version, "created_version": conversation.sync_version})
            if message.sender_id != request.user.pk or message.conversation_id != conversation.pk:
                transaction.set_rollback(True)
                return _error("This send token belongs to a different message. Please compose a new message.", 409)
            upload = form.cleaned_data.get("attachment")
            if created and upload:
                message.attachment.save(upload.name, upload, save=False)
                written = message.attachment.name
                message.attachment_name = upload.chat_display_name
                message.attachment_type = upload.chat_content_type
                message.save(update_fields=["attachment", "attachment_name", "attachment_type"])
    except Exception as error:
        if written:
            try: Message._meta.get_field("attachment").storage.delete(written)
            except OSError: pass
        if isinstance(error, OSError):
            return _error("The attachment could not be saved. Your message was not sent. Please retry.", 503)
        raise
    return JsonResponse({"entry": _entry(message, request.user)}, status=201 if created else 200)


@login_required
@require_GET
def attachment(request, pk):
    message = get_object_or_404(Message.objects.filter(
        Q(conversation__first_user=request.user) | Q(conversation__second_user=request.user)), pk=pk, deleted_at__isnull=True)
    if not message.attachment:
        raise Http404("Attachment unavailable")
    try:
        stream = message.attachment.open("rb")
    except OSError as error:
        raise Http404("Attachment unavailable") from error
    response = FileResponse(stream, as_attachment=True, filename=message.attachment_name, content_type=message.attachment_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def _valid_uuid(value):
    from uuid import UUID
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@require_POST
@session_guard
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
    attachment_file = message.attachment.name
    changes = {"edited_at": now, "body": form.cleaned_data["body"]} if action == "edit" else {
        "edited_at": now, "deleted_at": now, "body": "", "attachment": "", "attachment_name": "", "attachment_type": ""}
    with transaction.atomic():
        Conversation.objects.filter(pk=message.conversation_id).update(sync_version=F("sync_version") + 1)
        version = Conversation.objects.values_list("sync_version", flat=True).get(pk=message.conversation_id)
        changed = Message.objects.filter(pk=pk, sender=request.user, edited_at=revision, deleted_at__isnull=True).update(**changes, sync_version=version)
    if not changed:
        return _error("This message changed in another tab or was deleted. Refresh the chat before trying again.", 409)
    if action == "delete" and attachment_file:
        from .signals import remove_attachment
        transaction.on_commit(lambda: remove_attachment(attachment_file))
    message.refresh_from_db()
    return JsonResponse({"message": "Message updated." if action == "edit" else "Message deleted.", "entry": _entry(message, request.user)})
