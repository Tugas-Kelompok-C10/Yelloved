from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse
from .forms import AddressForm, NotificationPreferenceForm, PaymentMethodForm, ProfileForm
from .models import Address, NotificationPreference, PaymentMethod, Profile
from items.models import Item
from wanted_board.models import WantedPost


def _saved(request, message, route):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"message": message, "url": reverse(route)})
    messages.success(request, message)
    return redirect(route)

class AccountLoginView(LoginView):
    template_name = "account_profile/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Welcome back to Yelloved!")
        return response


def register(request):
    if request.user.is_authenticated:
        return redirect("show_main")

    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return _saved(request, "Your account has been created. Welcome to Yelloved!", "show_main")

    return render(request, "account_profile/register.html", {"form": form, "name": "Yelloved"})

def show_account_profile(request):
    profile = None
    form = None
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        form = ProfileForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=profile, user=request.user)
        if request.method == "POST" and form.is_valid():
            form.save()
            return _saved(request, "Your profile has been updated.", "account_profile:profile")
    return render(request, "account_profile/biodata.html", {
        "name": "Yelloved",
        "profile": profile,
        "form": form,
    })


def user_profile(request, username):
    profile_user = get_object_or_404(get_user_model(), username=username)
    profile = Profile.objects.filter(user=profile_user).first()
    active_tab = request.GET.get("tab", "posted")
    if active_tab not in {"posted", "wanted", "reviews"}:
        active_tab = "posted"
    return render(request, "account_profile/user_profile.html", {
        "name": "Yelloved",
        "profile_user": profile_user,
        "profile": profile,
        "items": Item.objects.filter(owner=profile_user, source="user").order_by("-created_at", "-pk"),
        "wanted_posts": WantedPost.objects.filter(requester=profile_user).order_by("-created_at"),
        "is_own_profile": request.user.is_authenticated and request.user.pk == profile_user.pk,
        "active_tab": active_tab,
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
            return _saved(request, "Address added successfully.", "account_profile:address_list")
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
    form = AddressForm(request.POST if request.method == "POST" else None, instance=address)
    if request.method == "POST" and form.is_valid():
        updated_address = form.save(commit=False)
        if updated_address.is_default:
            Address.objects.filter(user=request.user).exclude(id=address.id).update(is_default=False)
        updated_address.save()
        return _saved(request, "Address updated successfully.", "account_profile:address_list")
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
        return _saved(request, "Address deleted successfully.", "account_profile:address_list")
    return redirect("account_profile:address_list")


@login_required
@require_POST
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save(update_fields=["is_default"])
    return _saved(request, "Default address updated.", "account_profile:address_list")


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
            return _saved(request, "Payment method added successfully.", "account_profile:payment_methods")
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
    form = PaymentMethodForm(request.POST if request.method == "POST" else None, instance=method)
    if request.method == "POST" and form.is_valid():
        saved_method = form.save(commit=False)
        if saved_method.is_default:
            PaymentMethod.objects.filter(user=request.user).exclude(id=method.id).update(is_default=False)
        saved_method.save()
        return _saved(request, "Payment method updated successfully.", "account_profile:payment_methods")
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
        return _saved(request, "Payment method deleted successfully.", "account_profile:payment_methods")
    return redirect("account_profile:payment_methods")


@login_required
def notification_settings(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = NotificationPreferenceForm(request.POST if request.method == "POST" else None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _saved(request, "Notification preferences saved.", "account_profile:notifications")
    return render(request, "account_profile/notifications.html", {
        "name": "Yelloved",
        "profile": profile,
        "form": form,
    })


@login_required
def privacy_security(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = PasswordChangeForm(request.user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return _saved(request, "Your password has been updated.", "account_profile:privacy_security")
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
