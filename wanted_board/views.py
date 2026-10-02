from django.shortcuts import render


def show_wanted(request):
    return render(request, "wanted_post.html", {"name": "Yelloved"})
