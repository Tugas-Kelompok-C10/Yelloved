from django.shortcuts import render
from .models import Transaction


def transaction_home(request):
    return render(request, "transactions/transaction_home.html")


def checkout(request):
    return render(request, "transactions/checkout.html")


def transaction_history(request):
    if not request.user.is_authenticated:
        return render(
            request,
            "transactions/transaction_history.html",
            {"transactions": []}
        )

    transactions = Transaction.objects.filter(
        buyer=request.user
    ).order_by("-created_at")

    return render(
        request,
        "transactions/transaction_history.html",
        {"transactions": transactions}
    )