from django.shortcuts import render
from .models import Transaction
from account_profile.models import Profile


def transaction_home(request):
    return render(request, "transactions/transaction_home.html", {"name": "Yelloved"})




def checkout(request):
    context = {"name": "Yelloved", "errors": []}

    if request.method == "POST":
        recipient_name = request.POST.get("recipient_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        province_id = request.POST.get("province", "").strip()
        regency_id = request.POST.get("regency", "").strip()
        district_id = request.POST.get("district", "").strip()
        village_id = request.POST.get("village", "").strip()
        address = request.POST.get("address", "").strip()

        if not all([
            recipient_name,
            phone,
            province_id,
            regency_id,
            district_id,
            village_id,
            address,
        ]):
            context["errors"].append(
                "Semua kolom alamat pengiriman wajib diisi."
            )
        else:
            context["submitted"] = True
            context["recipient_name"] = recipient_name
            context["phone"] = phone
            context["shipping_address"] = (
                f"Nama Penerima: {recipient_name}\n"
                f"Nomor HP: {phone}\n"
                f"Provinsi (ID): {province_id}\n"
                f"Kota/Kabupaten (ID): {regency_id}\n"
                f"Kecamatan (ID): {district_id}\n"
                f"Kelurahan/Desa (ID): {village_id}\n"
                f"Alamat Lengkap: {address}"
            )

    return render(request, "transactions/checkout.html", context)





def transaction_history(request):
    if not request.user.is_authenticated:
        return render(
            request,
            "transactions/transaction_history.html",
            {
                "transactions": [],
                "name": "Yelloved",
                "active_status": "all",
            },
        )

    transactions = Transaction.objects.filter(
        buyer=request.user
    ).order_by("-created_at")

    active_status = request.GET.get("status", "all")

    if active_status == "pending":
        transactions = transactions.filter(payment_status="pending")
    elif active_status == "processing":
        transactions = transactions.filter(
            transaction_status="processing"
        )
    elif active_status == "completed":
        transactions = transactions.filter(
            transaction_status="completed"
        )
    elif active_status == "cancelled":
        transactions = transactions.filter(
            transaction_status="cancelled"
        )
    else:
        active_status = "all"

    return render(
        request,
        "transactions/transaction_history.html",
        {
            "transactions": transactions,
            "name": "Yelloved",
            "active_status": active_status,
        },
    )


def app_page(request):
    return render(
        request,
        "transactions/app.html",
        {"name": "Yelloved"}
    )


def pesan_page(request):
    profile = Profile.objects.get_or_create(user=request.user)[0] if request.user.is_authenticated else None
    return render(request, "transactions/pesan.html", {"name": "Yelloved", "profile": profile})

