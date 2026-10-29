from functools import wraps

from django.http import JsonResponse
from django.utils.crypto import constant_time_compare, salted_hmac


def chat_identity(request):
    if not request.user.is_authenticated:
        return ""
    value = f"{request.user.pk}:{request.session.session_key}:{request.session.get('_auth_user_hash', '')}"
    return salted_hmac("chat.session", value).hexdigest()


def session_guard(view):
    """Reject an old chat tab before it can send under a different account."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        current = chat_identity(request)
        expected = request.headers.get("X-Chat-Session")
        if not current:
            response = JsonResponse({"code": "chat_session_changed", "message": "Your session has expired. Reload Chat and sign in again."}, status=401)
        elif expected and not constant_time_compare(expected, current):
            response = JsonResponse({"code": "chat_session_changed", "message": "Your account or session changed in another tab. Reload Chat to continue."}, status=409)
        else:
            response = view(request, *args, **kwargs)
        response["X-Chat-Session"] = current
        response["Cache-Control"] = "private, no-store"
        return response
    return wrapped
