from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


def show_main(request):
    context = {
        "name": "Yelloved",
        "heart_count": request.session.get("landing_hearts", 0),
    }
    return render(request, "index.html", context)


@require_POST
def send_love(request):
    """A playful, session-scoped interaction; no account or global metric required."""
    count = request.session.get("landing_hearts", 0) + 1
    request.session["landing_hearts"] = count
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"count": count})
    return redirect("show_main")
