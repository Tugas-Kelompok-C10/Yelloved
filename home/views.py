from django.shortcuts import render


def show_main(request):
    context = {
        "name": "Yelloved"
    }
    return render(request, "index.html", context)
