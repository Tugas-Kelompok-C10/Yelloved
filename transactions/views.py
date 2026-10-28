from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction as db_transaction
from django.contrib import messages

from .models import Transaction, CartItem
from items.models import Item
from account_profile.models import Profile, Address


def cart_view(request):
    if not request.user.is_authenticated:
        return redirect("login")

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related("item")

    return render(
        request,
        "transactions/cart.html",
        {
            "name": "Yelloved",
            "cart_items": cart_items,
        },
    )


def add_to_cart(request, item_id):
    if not request.user.is_authenticated:
        return redirect("login")

    if request.method != "POST":
        return redirect("items:explore")

    item = get_object_or_404(Item, pk=item_id)

    if (
        item.owner_id == request.user.id
        or item.status != Item.Status.AVAILABLE
        or item.listing_type != Item.ListingType.SALE
    ):
        messages.error(
            request,
            "Barang ini tidak bisa ditambahkan ke keranjang.",
        )
        return redirect(item.get_absolute_url())

    _, created = CartItem.objects.get_or_create(
        user=request.user,
        item=item,
    )

    if created:
        messages.success(request, "Barang berhasil ditambahkan ke keranjang.")
    else:
        messages.info(request, "Barang ini sudah ada di keranjang.")

    return redirect("transactions:cart")

def transaction_home(request):
    return render(
        request,
        "transactions/transaction_home.html",
        {"name": "Yelloved"},
    )


def checkout(request):
    context = {
        "name": "Yelloved",
        "errors": [],
    }

    if not request.user.is_authenticated:
        context["errors"].append(
            "Silakan login terlebih dahulu untuk melanjutkan checkout."
        )
        return render(request, "transactions/checkout.html", context)

    allowed_payment_methods = {"qris", "bank_transfer"}
    allowed_banks = {"bca", "bni", "bri", "mandiri", "permata"}

    def get_addresses():
        return Address.objects.filter(user=request.user).order_by(
            "-is_default", "label", "recipient_name"
        )

    def get_selected_address():
        address_id = request.session.get("checkout_address_id")

        if address_id:
            address = get_addresses().filter(id=address_id).first()
            if address:
                return address

        return (
            get_addresses().filter(is_default=True).first()
            or get_addresses().first()
        )

    if request.method == "POST":
        action = request.POST.get("action", "select_address")

        # ==========================================
        # SIMPAN / EDIT ALAMAT
        # ==========================================
        if action == "save_address":
            address_id = request.POST.get("address_id", "").strip()
            recipient_name = request.POST.get("recipient_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            province = request.POST.get("province", "").strip()
            city = request.POST.get("regency", "").strip()
            district = request.POST.get("district", "").strip()
            village = request.POST.get("village", "").strip()
            postal_code = request.POST.get("postal_code", "").strip()
            street = request.POST.get("address", "").strip()
            label = request.POST.get("label", "Rumah").strip()
            is_default = request.POST.get("is_default") == "on"

            address = None

            if address_id:
                address = get_addresses().filter(id=address_id).first()

                if not address:
                    context["errors"].append(
                        "Alamat yang ingin diubah tidak ditemukan."
                    )
                    context["show_address_form"] = True

            if not context["errors"] and not all([
                recipient_name,
                phone,
                province,
                city,
                district,
                village,
                postal_code,
                street,
            ]):
                context["errors"].append(
                    "Lengkapi semua kolom alamat pengiriman."
                )
                context["show_address_form"] = True

            if not context["errors"]:
                full_street = f"{street}, Kel. {village}, Kec. {district}"

                with db_transaction.atomic():
                    if is_default:
                        get_addresses().filter(is_default=True).update(
                            is_default=False
                        )

                    if address:
                        address.recipient_name = recipient_name
                        address.phone_number = phone
                        address.province = province
                        address.city = city
                        address.postal_code = postal_code
                        address.street_address = full_street
                        address.label = label or "Rumah"
                        address.is_default = is_default
                        address.save()
                    else:
                        address = Address.objects.create(
                            user=request.user,
                            label=label or "Rumah",
                            recipient_name=recipient_name,
                            phone_number=phone,
                            street_address=full_street,
                            city=city,
                            province=province,
                            postal_code=postal_code,
                            is_default=is_default or not get_addresses().exists(),
                        )

                    # Jika belum ada alamat utama, tetapkan alamat pertama.
                    if not get_addresses().filter(is_default=True).exists():
                        address.is_default = True
                        address.save(update_fields=["is_default"])

                request.session["checkout_address_id"] = address.id
                return redirect(request.path)

        # ==========================================
        # PILIH ALAMAT CHECKOUT
        # ==========================================
        elif action == "select_address":
            address_id = request.POST.get("address_id", "").strip()
            selected_address = get_addresses().filter(id=address_id).first()

            if selected_address:
                request.session["checkout_address_id"] = selected_address.id
                return redirect(request.path)

            context["errors"].append(
                "Pilih alamat pengiriman yang valid."
            )

        # ==========================================
        # JADIKAN ALAMAT UTAMA
        # ==========================================
        elif action == "set_default":
            address_id = request.POST.get("address_id", "").strip()
            selected_address = get_addresses().filter(id=address_id).first()

            if selected_address:
                with db_transaction.atomic():
                    get_addresses().filter(is_default=True).update(
                        is_default=False
                    )

                    selected_address.is_default = True
                    selected_address.save(update_fields=["is_default"])

                request.session["checkout_address_id"] = selected_address.id
                return redirect(request.path)

            context["errors"].append(
                "Alamat yang ingin dijadikan utama tidak ditemukan."
            )

        # ==========================================
        # SIMPAN METODE PEMBAYARAN
        # ==========================================
        elif action == "select_payment":
            payment_method = request.POST.get("payment_method", "").strip()
            bank = request.POST.get("bank", "").strip().lower()

            if payment_method not in allowed_payment_methods:
                context["errors"].append(
                    "Pilih metode pembayaran yang valid."
                )

            elif payment_method == "bank_transfer" and bank not in allowed_banks:
                context["errors"].append(
                    "Pilih bank untuk pembayaran Virtual Account."
                )

            else:
                request.session["checkout_payment_method"] = payment_method

                if payment_method == "bank_transfer":
                    request.session["checkout_bank"] = bank
                else:
                    request.session.pop("checkout_bank", None)

                request.session.modified = True
                return redirect(request.path)

    # ==========================================
    # DATA UNTUK TEMPLATE
    # ==========================================
    context["addresses"] = get_addresses()
    context["selected_address"] = get_selected_address()
    context["default_address"] = get_addresses().filter(
        is_default=True
    ).first()

    context["selected_payment_method"] = request.session.get(
        "checkout_payment_method", "qris"
    )
    context["selected_bank"] = request.session.get(
        "checkout_bank", ""
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
        {"name": "Yelloved"},
    )


def pesan_page(request):
    profile = (
        Profile.objects.get_or_create(user=request.user)[0]
        if request.user.is_authenticated
        else None
    )

    return render(
        request,
        "transactions/pesan.html",
        {"name": "Yelloved", "profile": profile},
    )
