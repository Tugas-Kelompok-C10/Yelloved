import uuid
import requests
from urllib.parse import urlparse
from django.http import HttpResponse
from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from account_profile.models import Address

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from items.models import Item
from .models import CartItem, Transaction, TransactionItem


# GET: Menampilkan isi keranjang
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cart_api(request):
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related("item")
    )

    results = []

    for entry in cart_items:
        item = entry.item

        results.append({
            "cart_item_id": entry.id,
            "quantity": entry.quantity,
            "item": {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "category": item.category,
                "condition": item.condition,
                "price": str(item.price) if item.price is not None else None,
                "currency": item.currency,
                "price_display": item.price_display,
                "listing_type": item.listing_type,
                "status": item.status,
                "location": item.location,
                "image_url": request.build_absolute_uri(
                    item.display_image_url
                ),
            },
        })

    return Response({
        "cart_count": len(results),
        "results": results,
    })


# DELETE: Menghapus item dari keranjang
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_cart_api(request, cart_item_id):
    cart_item = get_object_or_404(
        CartItem,
        id=cart_item_id,
        user=request.user
    )

    cart_item.delete()

    return Response({
        "message": "Item berhasil dihapus dari keranjang."
    }, status=status.HTTP_200_OK)



# POST: Menambahkan item ke keranjang
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_cart_api(request, item_id):
    item = get_object_or_404(Item, pk=item_id)

    if item.owner_id == request.user.id:
        return Response({
            "message": "Kamu tidak bisa membeli barang milik sendiri."
        }, status=status.HTTP_400_BAD_REQUEST)

    if item.listing_type != Item.ListingType.SALE:
        return Response({
            "message": "Hanya barang yang dijual yang bisa dimasukkan ke keranjang."
        }, status=status.HTTP_400_BAD_REQUEST)

    if item.status != Item.Status.AVAILABLE:
        return Response({
            "message": "Barang sudah tidak tersedia."
        }, status=status.HTTP_400_BAD_REQUEST)

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        item=item,
        defaults={"quantity": 1}
    )

    # Setiap listing hanya memiliki satu unit.
    if not created and cart_item.quantity != 1:
        cart_item.quantity = 1
        cart_item.save(update_fields=["quantity"])

    cart_count = CartItem.objects.filter(
        user=request.user
    ).count()

    return Response({
        "created": created,
        "message": (
            "Item berhasil ditambahkan ke keranjang."
            if created
            else "Item sudah ada di keranjang."
        ),
        "cart_item_id": cart_item.id,
        "quantity": 1,
        "cart_count": cart_count,
    }, status=status.HTTP_200_OK)



# PATCH: Memastikan quantity sesuai stok listing
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_cart_api(request, cart_item_id):
    cart_item = get_object_or_404(
        CartItem,
        id=cart_item_id,
        user=request.user
    )

    quantity = request.data.get("quantity")

    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity != 1
    ):
        return Response({
            "message": "Setiap listing hanya tersedia satu unit."
        }, status=status.HTTP_400_BAD_REQUEST)

    cart_item.quantity = 1
    cart_item.save(update_fields=["quantity"])

    return Response({
        "message": "Quantity berhasil diperbarui.",
        "cart_item_id": cart_item.id,
        "quantity": 1,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def address_list_api(request):
    addresses = Address.objects.filter(
        user=request.user
    ).order_by("-is_default", "label", "recipient_name")

    results = []

    for address in addresses:
        results.append({
            "id": address.id,
            "label": address.label,
            "recipient_name": address.recipient_name,
            "phone_number": address.phone_number,
            "street_address": address.street_address,
            "city": address.city,
            "province": address.province,
            "postal_code": address.postal_code,
            "latitude": str(address.latitude) if address.latitude is not None else None,
            "longitude": str(address.longitude) if address.longitude is not None else None,
            "is_default": address.is_default,
        })

    return Response({
        "address_count": len(results),
        "results": results,
    })


# POST: Checkout menggunakan metode COD
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout_cod_api(request):
    cart_item_ids = request.data.get("cart_item_ids")
    meeting_location = request.data.get("cod_meeting_location", "").strip()
    meeting_time_raw = request.data.get("cod_meeting_time", "").strip()

    # Validasi daftar item
    if (
        not isinstance(cart_item_ids, list)
        or not cart_item_ids
        or any(
            not isinstance(item_id, int) or isinstance(item_id, bool)
            for item_id in cart_item_ids
        )
        or len(cart_item_ids) != len(set(cart_item_ids))
    ):
        return Response({
            "message": "Pilih minimal satu item keranjang yang valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi lokasi pertemuan
    if not meeting_location:
        return Response({
            "message": "Lokasi pertemuan wajib diisi."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi waktu pertemuan
    meeting_time = parse_datetime(meeting_time_raw)

    if not meeting_time:
        return Response({
            "message": "Format waktu pertemuan tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    if timezone.is_naive(meeting_time):
        meeting_time = timezone.make_aware(
            meeting_time,
            timezone.get_current_timezone()
        )

    # Ambil item yang dipilih milik pengguna
    cart_entries = list(
        CartItem.objects
        .filter(
            user=request.user,
            id__in=cart_item_ids
        )
        .select_related("item")
    )

    if len(cart_entries) != len(cart_item_ids):
        return Response({
            "message": "Ada item keranjang yang tidak ditemukan."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi kelayakan setiap barang
    for entry in cart_entries:
        item = entry.item

        if (
            item.owner_id == request.user.id
            or item.status != Item.Status.AVAILABLE
            or item.listing_type != Item.ListingType.SALE
            or item.price is None
        ):
            return Response({
                "message": f"Barang '{item.title}' sudah tidak bisa dibeli."
            }, status=status.HTTP_400_BAD_REQUEST)

    # Setiap listing preloved hanya satu unit
    total = sum(
        (entry.item.price for entry in cart_entries),
        start=0
    )

    item_names = ", ".join(
        entry.item.title for entry in cart_entries
    )[:255]

    try:
        with db_transaction.atomic():
            order = Transaction.objects.create(
                order_id=f"COD-{uuid.uuid4().hex[:16].upper()}",
                buyer=request.user,
                item_name=item_names,
                quantity=len(cart_entries),
                total_amount=total,
                payment_method="cod",
                cod_meeting_location=meeting_location,
                cod_meeting_time=meeting_time,
                shipping_address=f"COD - Campus meeting: {meeting_location}",
                payment_status="pending",
                transaction_status="pending",
            )

            # Simpan informasi seller untuk kebutuhan review
            TransactionItem.objects.bulk_create([
                TransactionItem(
                    transaction=order,
                    item=entry.item,
                    seller_id=entry.item.owner_id
                )
                for entry in cart_entries
            ])

            # Hapus hanya item yang berhasil di-checkout
            CartItem.objects.filter(
                user=request.user,
                id__in=cart_item_ids
            ).delete()

    except Exception:
        return Response({
            "message": "Gagal membuat transaksi. Silakan coba kembali."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        "message": "Checkout COD berhasil dibuat.",
        "order_id": order.order_id,
        "item_name": order.item_name,
        "quantity": order.quantity,
        "total_amount": str(order.total_amount),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "transaction_status": order.transaction_status,
        "cod_meeting_location": order.cod_meeting_location,
        "cod_meeting_time": order.cod_meeting_time.isoformat(),
    }, status=status.HTTP_201_CREATED)


# POST: Checkout menggunakan QRIS Midtrans
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout_qris_api(request):
    cart_item_ids = request.data.get("cart_item_ids")
    address_id = request.data.get("address_id")

    # Validasi daftar item
    if (
        not isinstance(cart_item_ids, list)
        or not cart_item_ids
        or any(
            not isinstance(item_id, int) or isinstance(item_id, bool)
            for item_id in cart_item_ids
        )
        or len(cart_item_ids) != len(set(cart_item_ids))
    ):
        return Response({
            "message": "Pilih minimal satu item keranjang yang valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi alamat
    if not isinstance(address_id, int) or isinstance(address_id, bool):
        return Response({
            "message": "Alamat pengiriman tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    address = get_object_or_404(
        Address,
        id=address_id,
        user=request.user
    )

    # Ambil item keranjang milik pengguna
    cart_entries = list(
        CartItem.objects
        .filter(
            user=request.user,
            id__in=cart_item_ids
        )
        .select_related("item")
    )

    if len(cart_entries) != len(cart_item_ids):
        return Response({
            "message": "Ada item keranjang yang tidak ditemukan."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi barang
    for entry in cart_entries:
        item = entry.item

        if (
            item.owner_id == request.user.id
            or item.status != Item.Status.AVAILABLE
            or item.listing_type != Item.ListingType.SALE
            or item.price is None
        ):
            return Response({
                "message": f"Barang '{item.title}' sudah tidak bisa dibeli."
            }, status=status.HTTP_400_BAD_REQUEST)

    total = sum(
        (entry.item.price for entry in cart_entries),
        start=0
    )

    if total <= 0:
        return Response({
            "message": "Total pembayaran tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    item_names = ", ".join(
        entry.item.title for entry in cart_entries
    )[:255]

    address_parts = [
        address.recipient_name,
        address.phone_number,
        address.street_address,
        address.city,
        address.province,
        address.postal_code,
    ]

    shipping_address = ", ".join(
        str(part).strip()
        for part in address_parts
        if part
    )

    try:
        with db_transaction.atomic():
            order = Transaction.objects.create(
                order_id=f"YL-{uuid.uuid4().hex[:16].upper()}",
                buyer=request.user,
                item_name=item_names,
                quantity=len(cart_entries),
                total_amount=total,
                payment_method="qris",
                shipping_address=shipping_address,
                payment_status="pending",
                transaction_status="pending",
            )

            # Simpan informasi seller untuk kebutuhan review
            TransactionItem.objects.bulk_create([
                TransactionItem(
                    transaction=order,
                    item=entry.item,
                    seller_id=entry.item.owner_id
                )
                for entry in cart_entries
            ])

    except Exception:
        return Response({
            "message": "Gagal membuat transaksi."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Buat pembayaran melalui Midtrans
    try:
        from .views import create_midtrans_payment

        create_midtrans_payment(
            order=order,
            payment_method="qris",
        )

    except Exception:
        return Response({
            "message": (
                "Gagal membuat pembayaran QRIS. "
                "Keranjang belum dikosongkan. "
                "Silakan coba kembali."
            ),
        }, status=status.HTTP_502_BAD_GATEWAY)

    # Hapus item keranjang setelah Midtrans berhasil
    CartItem.objects.filter(
        user=request.user,
        id__in=cart_item_ids
    ).delete()

    return Response({
        "message": "Checkout QRIS berhasil dibuat.",
        "order_id": order.order_id,
        "item_name": order.item_name,
        "quantity": order.quantity,
        "total_amount": str(order.total_amount),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "transaction_status": order.transaction_status,
        "qr_code_url": order.midtrans_qr_code_url,
        "expiry_time": (
            order.midtrans_expiry_time.isoformat()
            if order.midtrans_expiry_time
            else None
        ),
    }, status=status.HTTP_201_CREATED)


# GET: Mengambil detail transaksi pengguna
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_detail_api(request, order_id):
    order = get_object_or_404(
        Transaction,
        order_id=order_id,
        buyer=request.user
    )

    # Sinkronisasi status pembayaran QRIS/VA dengan Midtrans
    if order.payment_method in {"qris", "va"}:
        from .views import sync_midtrans_status
        sync_midtrans_status(order)

    return Response({
        "order_id": order.order_id,
        "item_name": order.item_name,
        "quantity": order.quantity,
        "total_amount": str(order.total_amount),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "transaction_status": order.transaction_status,
        "shipping_address": order.shipping_address,
        "cod_meeting_location": order.cod_meeting_location,
        "cod_meeting_time": (
            order.cod_meeting_time.isoformat()
            if order.cod_meeting_time else None
        ),
        "qr_code_url": order.midtrans_qr_code_url,
        "virtual_account_bank": order.virtual_account_bank,
        "virtual_account_number": order.virtual_account_number,
        "virtual_account_bill_key": order.virtual_account_bill_key,
        "virtual_account_biller_code": order.virtual_account_biller_code,
        "expiry_time": (
            order.midtrans_expiry_time.isoformat()
            if order.midtrans_expiry_time else None
        ),
        "created_at": order.created_at.isoformat(),
    }, status=status.HTTP_200_OK)



# POST: Checkout menggunakan Virtual Account Midtrans
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout_va_api(request):
    cart_item_ids = request.data.get("cart_item_ids")
    address_id = request.data.get("address_id")
    bank_code = request.data.get("bank_code", "").lower().strip()

    allowed_banks = {
        "bca", "bni", "bri", "mandiri", "permata"
    }

    # Validasi daftar item
    if (
        not isinstance(cart_item_ids, list)
        or not cart_item_ids
        or any(
            not isinstance(item_id, int) or isinstance(item_id, bool)
            for item_id in cart_item_ids
        )
        or len(cart_item_ids) != len(set(cart_item_ids))
    ):
        return Response({
            "message": "Pilih minimal satu item keranjang yang valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi alamat
    if not isinstance(address_id, int) or isinstance(address_id, bool):
        return Response({
            "message": "Alamat pengiriman tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    address = get_object_or_404(
        Address,
        id=address_id,
        user=request.user
    )

    # Validasi bank
    if bank_code not in allowed_banks:
        return Response({
            "message": "Bank Virtual Account tidak didukung."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Ambil item keranjang
    cart_entries = list(
        CartItem.objects
        .filter(
            user=request.user,
            id__in=cart_item_ids
        )
        .select_related("item")
    )

    if len(cart_entries) != len(cart_item_ids):
        return Response({
            "message": "Ada item keranjang yang tidak ditemukan."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validasi barang
    for entry in cart_entries:
        item = entry.item

        if (
            item.owner_id == request.user.id
            or item.status != Item.Status.AVAILABLE
            or item.listing_type != Item.ListingType.SALE
            or item.price is None
        ):
            return Response({
                "message": f"Barang '{item.title}' sudah tidak bisa dibeli."
            }, status=status.HTTP_400_BAD_REQUEST)

    total = sum(
        (entry.item.price for entry in cart_entries),
        start=0
    )

    if total <= 0:
        return Response({
            "message": "Total pembayaran tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    item_names = ", ".join(
        entry.item.title for entry in cart_entries
    )[:255]

    address_parts = [
        address.recipient_name,
        address.phone_number,
        address.street_address,
        address.city,
        address.province,
        address.postal_code,
    ]

    shipping_address = ", ".join(
        str(part).strip()
        for part in address_parts
        if part
    )

    try:
        with db_transaction.atomic():
            order = Transaction.objects.create(
                order_id=f"YL-{uuid.uuid4().hex[:16].upper()}",
                buyer=request.user,
                item_name=item_names,
                quantity=len(cart_entries),
                total_amount=total,
                payment_method="va",
                shipping_address=shipping_address,
                payment_status="pending",
                transaction_status="pending",
            )

            TransactionItem.objects.bulk_create([
                TransactionItem(
                    transaction=order,
                    item=entry.item,
                    seller_id=entry.item.owner_id
                )
                for entry in cart_entries
            ])

    except Exception:
        return Response({
            "message": "Gagal membuat transaksi."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Membuat Virtual Account melalui Midtrans
    try:
        from .views import create_midtrans_payment

        create_midtrans_payment(
            order=order,
            payment_method="va",
            bank_code=bank_code,
        )

    except Exception:
        return Response({
            "message": (
                "Gagal membuat Virtual Account. "
                "Keranjang belum dikosongkan. "
                "Silakan coba kembali."
            ),
        }, status=status.HTTP_502_BAD_GATEWAY)

    # Hapus item setelah pembayaran berhasil dibuat
    CartItem.objects.filter(
        user=request.user,
        id__in=cart_item_ids
    ).delete()

    return Response({
        "message": "Checkout Virtual Account berhasil dibuat.",
        "order_id": order.order_id,
        "item_name": order.item_name,
        "quantity": order.quantity,
        "total_amount": str(order.total_amount),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "transaction_status": order.transaction_status,
        "virtual_account_bank": order.virtual_account_bank,
        "virtual_account_number": order.virtual_account_number,
        "virtual_account_bill_key": order.virtual_account_bill_key,
        "virtual_account_biller_code": order.virtual_account_biller_code,
        "expiry_time": (
            order.midtrans_expiry_time.isoformat()
            if order.midtrans_expiry_time
            else None
        ),
    }, status=status.HTTP_201_CREATED)


# GET: Menampilkan riwayat transaksi pengguna
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history_api(request):
    from .views import sync_midtrans_status

    active_type = request.query_params.get("type", "bought")

    if active_type not in {"bought", "sold"}:
        return Response({
            "message": "Tipe transaksi harus bought atau sold."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Ambil transaksi berdasarkan tipe
    if active_type == "sold":
        transactions = Transaction.objects.filter(
            review_items__seller=request.user
        ).distinct()
    else:
        transactions = Transaction.objects.filter(
            buyer=request.user
        )

    transactions = transactions.order_by("-created_at")

    # Sinkronisasi pembayaran online yang masih pending
    pending_orders = transactions.filter(
        payment_status="pending",
        transaction_status="pending",
        payment_method__in=["qris", "va"],
    )[:10]

    for order in pending_orders:
        sync_midtrans_status(order)

    # Filter status transaksi
    active_status = request.query_params.get("status", "all")

    if active_status == "pending":
        transactions = transactions.filter(
            payment_status="pending"
        )
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
    elif active_status != "all":
        return Response({
            "message": "Filter status tidak valid."
        }, status=status.HTTP_400_BAD_REQUEST)

    results = []

    for order in transactions:
        results.append({
            "id": order.id,
            "order_id": order.order_id,
            "item_name": order.item_name,
            "quantity": order.quantity,
            "total_amount": str(order.total_amount),
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "transaction_status": order.transaction_status,
            "shipping_address": order.shipping_address,
            "cod_meeting_location": order.cod_meeting_location,
            "cod_meeting_time": (
                order.cod_meeting_time.isoformat()
                if order.cod_meeting_time else None
            ),
            "created_at": order.created_at.isoformat(),
        })

    return Response({
        "type": active_type,
        "status": active_status,
        "transaction_count": len(results),
        "results": results,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_qris_image_api(request, order_id):
    try:
        transaction = Transaction.objects.get(
            order_id=order_id,
            buyer=request.user,
        )
    except Transaction.DoesNotExist:
        return Response(
            {"error": "Transaksi tidak ditemukan."},
            status=404,
        )

    if transaction.payment_method.lower() != "qris":
        return Response(
            {"error": "Transaksi ini bukan pembayaran QRIS."},
            status=400,
        )

    qr_url = transaction.midtrans_qr_code_url

    if not qr_url:
        return Response(
            {"error": "QR Code tidak tersedia."},
            status=404,
        )

    parsed_url = urlparse(qr_url)

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "merchants-app.sbx.midtrans.com"
    ):
        return Response(
            {"error": "URL QRIS tidak valid."},
            status=400,
        )

    try:
        qr_response = requests.get(
            qr_url,
            timeout=15,
            allow_redirects=False,
        )

        if qr_response.status_code != 200:
            return Response(
                {"error": "Gagal mengambil gambar QRIS dari Midtrans."},
                status=502,
            )

        content_type = qr_response.headers.get("Content-Type", "")

        if not content_type.startswith("image/"):
            return Response(
                {"error": "Respons Midtrans bukan gambar."},
                status=502,
            )

        response = HttpResponse(
            qr_response.content,
            content_type=content_type,
        )
        response["Cache-Control"] = "private, no-store"
        return response

    except requests.RequestException:
        return Response(
            {"error": "Tidak dapat menghubungi server Midtrans."},
            status=502,
        )