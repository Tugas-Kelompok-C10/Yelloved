from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

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

    return render(request, "registration/register.html", {"form": form, "name": "Yelloved"})

def show_account_profile(request):
    return render(request, "account_profile.html", {"name": "Yelloved"})
