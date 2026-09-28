from django.shortcuts import render


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
    return render(request, "wanted_post.html", context)

def show_activity(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)