from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


def register(request):
    if request.user.is_authenticated:
        return redirect("home:show_main")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Akun berhasil dibuat. Selamat datang!")
        return redirect("home:show_main")

    return render(request, "registration/register.html", {"form": form, "name": "Yelloved"})


def show_account_profile(request):
    return render(request, "account_profile.html", {"name": "Yelloved"})


def show_main(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)

def show_explore(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)

def show_wanted(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)

def show_activity(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)

def show_item_matching(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)
