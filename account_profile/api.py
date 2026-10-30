"""JSON API endpoints for the account profile module."""

import json
from functools import wraps

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import AddressForm, PaymentMethodForm, ProfileForm
from .models import Address, PaymentMethod, Profile


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return view(request, *args, **kwargs)

    return wrapped


def read_payload(request):
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        return request.POST.dict()
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
    return request.POST.dict()


def form_errors(form):
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


def profile_data(request, profile):
    photo_url = profile.photo.url if profile.photo else None
    return {
        "id": profile.id,
        "username": request.user.username,
        "first_name": request.user.first_name,
        "email": request.user.email,
        "photo": request.build_absolute_uri(photo_url) if photo_url else None,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "gender": profile.gender,
        "phone_number": profile.phone_number,
    }


def address_data(address):
    return {
        "id": address.id,
        "label": address.label,
        "recipient_name": address.recipient_name,
        "phone_number": address.phone_number,
        "street_address": address.street_address,
        "city": address.city,
        "province": address.province,
        "postal_code": address.postal_code,
        "is_default": address.is_default,
    }


def payment_data(method):
    return {
        "id": method.id,
        "method_type": method.method_type,
        "provider": method.provider,
        "account_name": method.account_name,
        "account_identifier": method.masked_identifier,
        "is_default": method.is_default,
    }




@api_login_required
@require_http_methods(["GET", "POST", "PATCH"])
def profile_api(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return JsonResponse(profile_data(request, profile))

    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    data = {
        "first_name": payload.get("first_name", request.user.first_name),
        "email": payload.get("email", request.user.email),
        "date_of_birth": payload.get("date_of_birth", profile.date_of_birth),
        "gender": payload.get("gender", profile.gender),
        "phone_number": payload.get("phone_number", profile.phone_number),
    }
    form = ProfileForm(data, request.FILES or None, instance=profile, user=request.user)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    form.save()
    return JsonResponse(profile_data(request, profile))


@api_login_required
@require_http_methods(["POST"])
def profile_photo_api(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if "photo" not in request.FILES:
        return JsonResponse({"errors": {"photo": ["Please choose a profile photo to upload."]}}, status=400)
    data = {
        "first_name": request.user.first_name,
        "email": request.user.email,
        "date_of_birth": profile.date_of_birth,
        "gender": profile.gender,
        "phone_number": profile.phone_number,
    }
    form = ProfileForm(data, request.FILES, instance=profile, user=request.user)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    form.save()
    return JsonResponse(profile_data(request, profile))


@api_login_required
@require_http_methods(["GET", "POST"])
def addresses_api(request):
    if request.method == "GET":
        addresses = Address.objects.filter(user=request.user)
        return JsonResponse({"results": [address_data(address) for address in addresses]})

    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    form = AddressForm(payload)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    with transaction.atomic():
        address = form.save(commit=False)
        address.user = request.user
        if address.is_default or not Address.objects.filter(user=request.user).exists():
            Address.objects.filter(user=request.user).update(is_default=False)
            address.is_default = True
        address.save()
    return JsonResponse(address_data(address), status=201)


@api_login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def address_detail_api(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == "GET":
        return JsonResponse(address_data(address))
    if request.method == "DELETE":
        was_default = address.is_default
        address.delete()
        if was_default:
            next_address = Address.objects.filter(user=request.user).first()
            if next_address:
                next_address.is_default = True
                next_address.save(update_fields=["is_default"])
        return JsonResponse({"deleted": True})

    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    existing = address_data(address)
    existing.update(payload)
    form = AddressForm(existing, instance=address)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    with transaction.atomic():
        updated = form.save(commit=False)
        if updated.is_default:
            Address.objects.filter(user=request.user).exclude(id=address.id).update(is_default=False)
        updated.save()
    return JsonResponse(address_data(updated))


@api_login_required
@require_http_methods(["POST"])
def address_default_api(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    with transaction.atomic():
        Address.objects.filter(user=request.user).update(is_default=False)
        address.is_default = True
        address.save(update_fields=["is_default"])
    return JsonResponse(address_data(address))


@api_login_required
@require_http_methods(["GET", "POST"])
def payment_methods_api(request):
    if request.method == "GET":
        methods = PaymentMethod.objects.filter(user=request.user)
        return JsonResponse({"results": [payment_data(method) for method in methods]})

    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    form = PaymentMethodForm(payload)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    with transaction.atomic():
        method = form.save(commit=False)
        method.user = request.user
        if method.is_default or not PaymentMethod.objects.filter(user=request.user).exists():
            PaymentMethod.objects.filter(user=request.user).update(is_default=False)
            method.is_default = True
        method.save()
    return JsonResponse(payment_data(method), status=201)


@api_login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def payment_method_detail_api(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    if request.method == "GET":
        return JsonResponse(payment_data(method))
    if request.method == "DELETE":
        was_default = method.is_default
        method.delete()
        if was_default:
            next_method = PaymentMethod.objects.filter(user=request.user).first()
            if next_method:
                next_method.is_default = True
                next_method.save(update_fields=["is_default"])
        return JsonResponse({"deleted": True})

    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    existing = {
        "method_type": method.method_type,
        "provider": method.provider,
        "account_name": method.account_name,
        "account_identifier": method.account_identifier,
        "is_default": method.is_default,
    }
    existing.update(payload)
    form = PaymentMethodForm(existing, instance=method)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    with transaction.atomic():
        updated = form.save(commit=False)
        if updated.is_default:
            PaymentMethod.objects.filter(user=request.user).exclude(id=method.id).update(is_default=False)
        updated.save()
    return JsonResponse(payment_data(updated))




@api_login_required
@require_http_methods(["POST"])
def change_password_api(request):
    payload = read_payload(request)
    if payload is None:
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)
    form = PasswordChangeForm(request.user, payload)
    if not form.is_valid():
        return JsonResponse({"errors": form_errors(form)}, status=400)
    user = form.save()
    update_session_auth_hash(request, user)
    return JsonResponse({"message": "Password updated successfully."})
