from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .forms import ProfileForm
from .forms import AddressForm
from .models import Address, Profile

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
