import uuid
import midtransclient
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.shortcuts import render, redirect
from django.db import transaction as db_transaction
from django.urls import reverse
from urllib.parse import urlencode
from .models import Transaction, CartItem
from items.models import Item
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import Http404
from django.views.decorators.http import require_POST
from account_profile.models import Address


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

    item_id = request.GET.get("item")

    selected_item = None
    if item_id and request.user.is_authenticated:
        selected_item = Item.objects.filter(
            pk=item_id,
            status=Item.Status.AVAILABLE,
            listing_type=Item.ListingType.SALE,
        ).exclude(owner=request.user).first()

    context["selected_item"] = selected_item

    if not request.user.is_authenticated:
        context["errors"].append(
            "Silakan login terlebih dahulu untuk melanjutkan checkout."
        )
        return render(request, "transactions/checkout.html", context)

    allowed_payment_methods = {"cod","qris", "bank_transfer"}
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
        # PROSES METODE PEMBAYARAN
        # ==========================================
        elif action == "select_payment":
            payment_method = request.POST.get(
                "payment_method", ""
            ).strip()

            print("DEBUG ACTION:", action)
            print("DEBUG PAYMENT METHOD:", payment_method)
            print("DEBUG POST DATA:", request.POST.dict())
            bank = request.POST.get("bank", "").strip().lower()

            if payment_method not in allowed_payment_methods:
                context["errors"].append(
                    "Pilih metode pembayaran yang valid."
                )

            elif (
                payment_method == "bank_transfer"
                and bank not in allowed_banks
            ):
                context["errors"].append(
                    "Pilih bank untuk pembayaran Virtual Account."
                )

            elif payment_method == "cod":
                meeting_location = request.POST.get(
                    "cod_meeting_location", ""
                ).strip()

                meeting_time_raw = request.POST.get(
                    "cod_meeting_time", ""
                ).strip()

                meeting_time = parse_datetime(meeting_time_raw)

                if not meeting_location or not meeting_time:
                    context["errors"].append(
                        "Lengkapi lokasi dan waktu pertemuan COD."
                    )
                else:
                    if timezone.is_naive(meeting_time):
                        meeting_time = timezone.make_aware(
                            meeting_time,
                            timezone.get_current_timezone(),
                        )

                    # Ambil barang yang akan dibeli.
                    if selected_item:
                        order_items = [{
                            "item": selected_item,
                            "quantity": 1,
                        }]
                    else:
                        order_items = list(
                            CartItem.objects.filter(
                                user=request.user
                            ).select_related("item")
                        )
                        order_items = [
                            {
                                "item": entry.item,
                                "quantity": entry.quantity,
                            }
                            for entry in order_items
                        ]

                    if not order_items:
                        context["errors"].append(
                            "Keranjang belanjamu masih kosong."
                        )
                    else:
                        total = sum(
                            (entry["item"].price or 0)
                            * entry["quantity"]
                            for entry in order_items
                        )

                        item_names = ", ".join(
                            entry["item"].title
                            for entry in order_items
                        )[:255]

                        total_quantity = sum(
                            entry["quantity"]
                            for entry in order_items
                        )

                        try:
                            with db_transaction.atomic():
                                order = Transaction.objects.create(
                                    order_id=f"COD-{uuid.uuid4().hex[:16].upper()}",
                                    buyer=request.user,
                                    item_name=item_names,
                                    quantity=total_quantity,
                                    total_amount=total,
                                    payment_method="cod",
                                    cod_meeting_location=meeting_location,
                                    cod_meeting_time=meeting_time,
                                    shipping_address=(
                                        f"COD - Pertemuan di kampus: "
                                        f"{meeting_location}"
                                    ),
                                    payment_status="pending",
                                    transaction_status="pending",
                                )

                                # Kosongkan keranjang hanya jika
                                # checkout berasal dari keranjang.
                                if not selected_item:
                                    CartItem.objects.filter(
                                        user=request.user
                                    ).delete()

                        except Exception as e:
                            print("ERROR CHECKOUT COD:", repr(e))
                            context["errors"].append(
                                f"Pesanan gagal dibuat: {e}"
                            )
                        
                        else:
                            request.session.pop(
                                "checkout_payment_method", None
                            )
                            request.session.pop("checkout_bank", None)
                            request.session.pop("checkout_address_id", None)

                            messages.success(
                                request,
                                f"Pesanan {order.order_id} berhasil dibuat! "
                                "Pembayaran dilakukan saat bertemu dengan penjual."
                            )

                            return redirect(
                                "transactions:checkout_success",
                                order_id=order.order_id,
                            )

            
            
            else:
                # Buat pesanan sementara di database untuk preview QRIS/VA.
                # Belum membuat pembayaran melalui Midtrans.

                request.session["checkout_payment_method"] = payment_method

                if payment_method == "bank_transfer":
                    request.session["checkout_bank"] = bank
                else:
                    request.session.pop("checkout_bank", None)

                request.session.modified = True

                selected_address = get_selected_address()

                if not selected_address:
                    context["errors"].append(
                        "Tambahkan alamat pengiriman sebelum melanjutkan."
                    )
                else:
                    if selected_item:
                        order_items = [{
                            "item": selected_item,
                            "quantity": 1,
                        }]
                    else:
                        cart_entries = list(
                            CartItem.objects.filter(
                                user=request.user
                            ).select_related("item")
                        )

                        order_items = [
                            {
                                "item": entry.item,
                                "quantity": entry.quantity,
                            }
                            for entry in cart_entries
                        ]

                    if not order_items:
                        context["errors"].append(
                            "Keranjang belanjamu masih kosong."
                        )
                    else:
                        total = sum(
                            (entry["item"].price or 0)
                            * entry["quantity"]
                            for entry in order_items
                        )

                        total_quantity = sum(
                            entry["quantity"]
                            for entry in order_items
                        )

                        item_names = ", ".join(
                            entry["item"].title
                            for entry in order_items
                        )[:255]

                        if total <= 0:
                            context["errors"].append(
                                "Total pembayaran tidak valid."
                            )
                        else:
                            order_id = (
                                f"YL-{uuid.uuid4().hex[:16].upper()}"
                            )

                            address_parts = [
                                selected_address.recipient_name,
                                selected_address.phone_number,
                                selected_address.street_address,
                                selected_address.city,
                                selected_address.province,
                                selected_address.postal_code,
                            ]

                            shipping_address = ", ".join(
                                str(part).strip()
                                for part in address_parts
                                if part
                            )

                            try:
                                with db_transaction.atomic():
                                    order = Transaction.objects.create(
                                        order_id=order_id,
                                        buyer=request.user,
                                        item_name=item_names,
                                        quantity=total_quantity,
                                        total_amount=total,
                                        payment_method=(
                                            "qris"
                                            if payment_method == "qris"
                                            else "va"
                                        ),
                                        shipping_address=shipping_address,
                                        payment_status="pending",
                                        transaction_status="pending",
                                    )

                            except Exception as e:
                                print("ERROR CHECKOUT:", repr(e))
                                context["errors"].append(
                                    "Pesanan gagal disimpan. Periksa terminal Django."
                                )

                            else:
                                try:
                                    create_midtrans_payment(
                                        order=order,
                                        payment_method=(
                                            "qris"
                                            if payment_method == "qris"
                                            else "va"
                                        ),
                                        bank_code=(
                                            bank
                                            if payment_method == "bank_transfer"
                                            else "bca"
                                        ),
                                    )

                                except Exception as e:
                                    print("\n========== ERROR MIDTRANS ==========")
                                    print("Tipe error:", type(e).__name__)
                                    print(
                                        "Pesan:",
                                        getattr(e, "message", None) or str(e)
                                    )
                                    print(
                                        "HTTP status:",
                                        getattr(e, "http_status_code", None)
                                    )
                                    print(
                                        "Respons API:",
                                        getattr(e, "api_response_dict", None)
                                    )
                                    print("====================================\n")

                                    context["errors"].append(
                                        "Pembayaran belum berhasil dibuat oleh Midtrans. "
                                        "Keranjangmu tidak dikosongkan. "
                                        "Periksa terminal Django untuk detail error."
                                    )

                                else:
                                    # Kosongkan keranjang hanya jika Midtrans berhasil
                                    # menerima permintaan pembuatan pembayaran.
                                    if not selected_item:
                                        CartItem.objects.filter(
                                            user=request.user
                                        ).delete()

                                    preview_params = {
                                        "method": (
                                            "qris"
                                            if payment_method == "qris"
                                            else "va"
                                        ),
                                        "order_id": order.order_id,
                                    }

                                    if payment_method == "bank_transfer":
                                        preview_params["bank"] = bank

                                    preview_url = reverse(
                                        "transactions:payment_preview"
                                    )
                                    query_string = urlencode(preview_params)

                                    return redirect(
                                        f"{preview_url}?{query_string}"
                                    )



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

    
    if selected_item:
        context["cart_items"] = [{
            "item": selected_item,
            "quantity": 1,
        }]
        context["total"] = selected_item.price or 0
    else:
        cart_items = CartItem.objects.filter(user=request.user).select_related("item").order_by("-added_at")
        selected_ids = request.session.get("checkout_cart_entry_ids")
        if selected_ids is not None:
            cart_items = cart_items.filter(pk__in=selected_ids)
        cart_items = list(cart_items)
        if selected_ids is not None and (not cart_items or len(cart_items) != len(selected_ids)
                                        or any(not cart_entry_eligible(entry, request.user) for entry in cart_items)):
            messages.error(request, "Your selected items changed or are no longer available. Please review your cart.")
            return redirect("transactions:cart")
        for entry in cart_items:
            entry.quantity = 1  # A preloved listing is a unique unit, regardless of legacy quantity.
        context["cart_items"] = cart_items
        context["total"] = sum((entry.item.price or 0) for entry in cart_items)



    return render(request, "transactions/checkout.html", context)



@login_required
def checkout_success(request, order_id):
    order = get_object_or_404(
        Transaction,
        order_id=order_id,
        buyer=request.user,
        payment_method="cod",
    )

    return render(
        request,
        "transactions/checkout_success.html",
        {"order": order},
    )


@login_required
def cancel_order(request, order_id):
    if request.method != "POST":
        return redirect(
            "transactions:checkout_success",
            order_id=order_id,
        )

    order = get_object_or_404(
        Transaction,
        order_id=order_id,
        buyer=request.user,
        payment_method="cod",
    )

    if order.transaction_status != "pending":
        messages.error(
            request,
            "Pesanan ini tidak dapat dibatalkan lagi.",
        )
    else:
        order.transaction_status = "cancelled"
        order.save(update_fields=["transaction_status", "updated_at"])

        messages.success(
            request,
            f"Pesanan {order.order_id} berhasil dibatalkan.",
        )

    return redirect(
        "transactions:checkout_success",
        order_id=order.order_id,
    )

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
        transaction_status__in=["pending", "processing"]
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


def cart_entry_eligible(entry, user):
    return (entry.item.status == Item.Status.AVAILABLE
            and entry.item.listing_type == Item.ListingType.SALE
            and entry.item.owner_id != user.pk and entry.item.price is not None)


def selected_cart_entries(request):
    try:
        ids = {int(value) for value in request.POST.getlist("selected_items")}
    except (ValueError, TypeError):
        raise Http404("Invalid cart selection")
    entries = list(CartItem.objects.filter(user=request.user, pk__in=ids).select_related("item"))
    if len(entries) != len(ids):
        raise Http404("Cart selection not found")
    return entries


@login_required
def cart_view(request):
    if request.method == "POST":
        entries = selected_cart_entries(request)
        action = request.POST.get("action")
        if not entries:
            messages.error(request, "Select at least one item first.")
        elif action == "remove_selected":
            CartItem.objects.filter(user=request.user, pk__in=[entry.pk for entry in entries]).delete()
            messages.success(request, "Selected items removed from your cart.")
        elif action == "checkout":
            if any(not cart_entry_eligible(entry, request.user) for entry in entries):
                messages.error(request, "Only available items from other sellers can be checked out.")
            else:
                request.session["checkout_cart_entry_ids"] = sorted(entry.pk for entry in entries)
                return redirect("transactions:checkout")
        else:
            messages.error(request, "Choose a valid cart action.")
        return redirect("transactions:cart")

    cart_items = list(CartItem.objects.filter(user=request.user).select_related("item", "item__owner").order_by("-added_at"))
    seller_groups = {}
    for entry in cart_items:
        entry.quantity = 1
        entry.checkout_eligible = cart_entry_eligible(entry, request.user)
        group = seller_groups.setdefault(entry.item.owner_id, {"seller": entry.item.owner, "entries": []})
        group["entries"].append(entry)
    selected = [entry for entry in cart_items if entry.checkout_eligible]
    total = sum((entry.item.price or 0) for entry in selected)
    return render(request, "transactions/cart.html", {
        "name": "Yelloved", "cart_items": cart_items, "total": total,
        "total_display": "Rp" + f"{total:,.0f}".replace(",", "."),
        "selected_count": len(selected), "seller_groups": list(seller_groups.values()),
    })


@login_required
@require_POST
def remove_from_cart(request, entry_id):
    entry = get_object_or_404(CartItem, pk=entry_id, user=request.user)
    entry.delete()
    messages.success(request, "Item removed from your cart.")
    return redirect("transactions:cart")


@login_required
def add_to_cart(request, item_id):
    if request.method != "POST":
        return redirect("items:explore_items")

    item = get_object_or_404(
        Item,
        pk=item_id,
        status=Item.Status.AVAILABLE,
        listing_type=Item.ListingType.SALE,
    )

    if item.owner_id == request.user.id:
        messages.error(request, "Kamu tidak bisa membeli barang milik sendiri.")
        return redirect("items:explore_items")

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        item=item,
        defaults={"quantity": 1},
    )

    if not created:
        if cart_item.quantity != 1:
            cart_item.quantity = 1
            cart_item.save(update_fields=["quantity"])
        messages.info(request, "This item is already in your cart.")
    else:
        messages.success(request, "Item added to your cart.")
    return redirect("transactions:cart")

def checkout_success_preview(request):
    return render(request, "transactions/checkout_success.html")


def payment_preview(request):
    payment_method = request.GET.get("method", "qris").lower()

    if payment_method not in {"qris", "va"}:
        payment_method = "qris"

    bank_names = {
        "bca": "BCA",
        "bni": "BNI",
        "bri": "BRI",
        "mandiri": "Mandiri",
        "permata": "Permata",
    }

    bank_code = request.GET.get("bank", "bca").lower()

    if bank_code not in bank_names:
        bank_code = "bca"

    order_id = request.GET.get("order_id")
    order = None

    if order_id and request.user.is_authenticated:
        order = get_object_or_404(
            Transaction,
            order_id=order_id,
            buyer=request.user,
            payment_method__in=["qris", "va"],
        )

    return render(
        request,
        "transactions/payment_instructions.html",
        {
            "payment_method": payment_method,
            "bank_code": bank_code,
            "bank_name": bank_names[bank_code],
            "order": order,
        },
    )

def create_midtrans_payment(order, payment_method, bank_code="bca"):
    """
    Membuat transaksi pembayaran melalui Midtrans Core API.
    Hanya menggunakan kredensial Sandbox pada tahap pengujian.
    """

    if not settings.MIDTRANS_SERVER_KEY or not settings.MIDTRANS_CLIENT_KEY:
        raise ValueError(
            "Konfigurasi kunci Midtrans belum lengkap."
        )

    core_api = midtransclient.CoreApi(
        is_production=False,
        server_key=settings.MIDTRANS_SERVER_KEY,
        client_key=settings.MIDTRANS_CLIENT_KEY,
    )

    amount = int(order.total_amount)

    params = {
        "transaction_details": {
            "order_id": order.order_id,
            "gross_amount": amount,
        },
        "item_details": [
            {
                "id": order.order_id,
                "price": amount,
                "quantity": 1,
                "name": order.item_name[:50],
            }
        ],
    }

    if payment_method == "qris":
        params["payment_type"] = "qris"
        params["qris"] = {
            "acquirer": "gopay",
        }

    elif payment_method == "va":
        if bank_code == "mandiri":
            params["payment_type"] = "echannel"
            params["echannel"] = {
                "bill_info1": "Yelloved",
                "bill_info2": order.order_id[:30],
            }

        elif bank_code in {"bca", "bni", "bri", "permata"}:
            params["payment_type"] = "bank_transfer"
            params["bank_transfer"] = {
                "bank": bank_code,
            }

        else:
            raise ValueError(
                "Bank Virtual Account tidak didukung."
            )

    else:
        raise ValueError(
            "Metode pembayaran tidak valid."
        )

    # Kirim permintaan pembayaran ke Midtrans.
    response = core_api.charge(params)

    # Simpan ID transaksi dari Midtrans.
    order.midtrans_transaction_id = (
        response.get("transaction_id") or ""
    )

    # Simpan informasi kedaluwarsa jika tersedia.
    expiry_time = response.get("expiry_time")

    if expiry_time:
        parsed_expiry = parse_datetime(expiry_time)

        if parsed_expiry and timezone.is_naive(parsed_expiry):
            parsed_expiry = timezone.make_aware(parsed_expiry)

        order.midtrans_expiry_time = parsed_expiry

    # Simpan URL kode QR jika respons menyediakannya.
    if payment_method == "qris":
        actions = response.get("actions", [])

        qr_action = next(
            (
                action
                for action in actions
                if action.get("name") == "generate-qr-code-v2"
            ),
            None,
        )

        if qr_action is None:
            qr_action = next(
                (
                    action
                    for action in actions
                    if action.get("name") == "generate-qr-code"
                ),
                None,
            )

        order.midtrans_qr_code_url = (
            qr_action.get("url", "") if qr_action else ""
        )

    # Simpan detail Virtual Account.
    if payment_method == "va":
        order.virtual_account_bank = bank_code

        if bank_code == "mandiri":
            order.virtual_account_bill_key = (
                response.get("bill_key", "")
            )
            order.virtual_account_biller_code = (
                response.get("biller_code", "")
            )

        else:
            va_numbers = response.get("va_numbers", [])

            if va_numbers:
                order.virtual_account_number = (
                    va_numbers[0].get("va_number", "")
                )
            elif response.get("permata_va_number"):
                order.virtual_account_number = (
                    response["permata_va_number"]
                )

    order.save()

    return response
