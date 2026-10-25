from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404, redirect, render
from .forms import AddressForm, NotificationPreferenceForm, PaymentMethodForm, ProfileForm
from .models import Address, NotificationPreference, PaymentMethod, Profile

# Create your views here.
def register(request):
    if request.user.is_authenticated:
        return redirect("show_main")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Akun berhasil dibuat. Selamat datang!")
        return redirect("show_main")

    return render(request, "account_profile/register.html", {"form": form, "name": "Yelloved"})

def show_account_profile(request):
    profile = None
    form = None
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        form = ProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Biodata berhasil diperbarui.")
            return redirect("account_profile:profile")
    return render(request, "account_profile/biodata.html", {
        "name": "Yelloved",
        "profile": profile,
        "form": form,
    })


@login_required
def show_address_list(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            if address.is_default:
                Address.objects.filter(user=request.user).update(is_default=False)
            if not Address.objects.filter(user=request.user).exists():
                address.is_default = True
            address.save()
            messages.success(request, "Alamat berhasil ditambahkan.")
            return redirect("account_profile:address_list")
    else:
        form = AddressForm()
    return render(request, "account_profile/address_list.html", {
        "name": "Yelloved",
        "profile": profile,
        "addresses": Address.objects.filter(user=request.user),
        "form": form,
        "editing": False,
    })


@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        updated_address = form.save(commit=False)
        if updated_address.is_default:
            Address.objects.filter(user=request.user).exclude(id=address.id).update(is_default=False)
        updated_address.save()
        messages.success(request, "Alamat berhasil diperbarui.")
        return redirect("account_profile:address_list")
    return render(request, "account_profile/address_list.html", {
        "name": "Yelloved",
        "profile": Profile.objects.get_or_create(user=request.user)[0],
        "addresses": Address.objects.filter(user=request.user),
        "form": form,
        "editing": True,
        "editing_address": address,
    })


@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == "POST":
        was_default = address.is_default
        address.delete()
        if was_default:
            next_address = Address.objects.filter(user=request.user).first()
            if next_address:
                next_address.is_default = True
                next_address.save(update_fields=["is_default"])
        messages.success(request, "Alamat berhasil dihapus.")
    return redirect("account_profile:address_list")


@login_required
@require_POST
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save(update_fields=["is_default"])
    messages.success(request, "Alamat utama berhasil diperbarui.")
    return redirect("account_profile:address_list")


@login_required
def show_payment_methods(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            method = form.save(commit=False)
            method.user = request.user
            if method.is_default:
                PaymentMethod.objects.filter(user=request.user).update(is_default=False)
            if not PaymentMethod.objects.filter(user=request.user).exists():
                method.is_default = True
            method.save()
            messages.success(request, "Metode pembayaran berhasil ditambahkan.")
            return redirect("account_profile:payment_methods")
    else:
        form = PaymentMethodForm()
    return render(request, "account_profile/payment_methods.html", {
        "name": "Yelloved",
        "profile": profile,
        "methods": PaymentMethod.objects.filter(user=request.user),
        "form": form,
        "editing": False,
    })


@login_required
def edit_payment_method(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    form = PaymentMethodForm(request.POST or None, instance=method)
    if request.method == "POST" and form.is_valid():
        saved_method = form.save(commit=False)
        if saved_method.is_default:
            PaymentMethod.objects.filter(user=request.user).exclude(id=method.id).update(is_default=False)
        saved_method.save()
        messages.success(request, "Metode pembayaran berhasil diperbarui.")
        return redirect("account_profile:payment_methods")
    return render(request, "account_profile/payment_methods.html", {
        "name": "Yelloved",
        "profile": Profile.objects.get_or_create(user=request.user)[0],
        "methods": PaymentMethod.objects.filter(user=request.user),
        "form": form,
        "editing": True,
        "editing_method": method,
    })


@login_required
def delete_payment_method(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    if request.method == "POST":
        was_default = method.is_default
        method.delete()
        if was_default:
            next_method = PaymentMethod.objects.filter(user=request.user).first()
            if next_method:
                next_method.is_default = True
                next_method.save(update_fields=["is_default"])
        messages.success(request, "Metode pembayaran berhasil dihapus.")
    return redirect("account_profile:payment_methods")


@login_required
def notification_settings(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = NotificationPreferenceForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Preferensi notifikasi berhasil disimpan.")
        return redirect("account_profile:notifications")
    return render(request, "account_profile/notifications.html", {
        "name": "Yelloved",
        "profile": profile,
        "form": form,
    })


@login_required
def privacy_security(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Kata sandi berhasil diperbarui.")
        return redirect("account_profile:privacy_security")
    return render(request, "account_profile/privacy_security.html", {
        "name": "Yelloved",
        "profile": profile,
        "form": form,
    })


@login_required
def profile_reviews(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    active_tab = request.GET.get("tab", "pending")
    if active_tab not in {"pending", "mine"}:
        active_tab = "pending"
    return render(request, "account_profile/reviews.html", {
        "name": "Yelloved",
        "profile": profile,
        "active_tab": active_tab,
        "period": request.GET.get("period", "3m"),
        "query": request.GET.get("q", ""),
    })


@login_required
def help_messages(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "account_profile/help_messages.html", {
        "name": "Yelloved",
        "profile": profile,
    })
