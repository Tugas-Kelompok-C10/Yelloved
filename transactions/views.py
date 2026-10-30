import uuid
import midtransclient
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.shortcuts import render, redirect
from django.db import transaction as db_transaction
from django.urls import reverse
from urllib.parse import urlencode
from .models import Transaction, CartItem, TransactionItem
from items.models import Item
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation
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
            "Please log in before proceeding to checkout."
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
        # SAVE / EDIT ADDRESS
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
            label = request.POST.get("label", "Home").strip()
            is_default = request.POST.get("is_default") == "on"

            address = None

            if address_id:
                address = get_addresses().filter(id=address_id).first()

                if not address:
                    context["errors"].append(
                        "The address you want to edit could not be found."
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
                    "Please complete all shipping address fields."
                )
                context["show_address_form"] = True

            if not context["errors"]:
                full_street = f"{street}, Subdistrict/Village {village}, District {district}"

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
                        address.label = label or "Home"
                        address.is_default = is_default
                        address.save()
                    else:
                        address = Address.objects.create(
                            user=request.user,
                            label=label or "Home",
                            recipient_name=recipient_name,
                            phone_number=phone,
                            street_address=full_street,
                            city=city,
                            province=province,
                            postal_code=postal_code,
                            is_default=is_default or not get_addresses().exists(),
                        )

                    # If no default address exists yet, set the first address as default.
                    if not get_addresses().filter(is_default=True).exists():
                        address.is_default = True
                        address.save(update_fields=["is_default"])

                request.session["checkout_address_id"] = address.id
                return redirect(request.path)

        # ==========================================
        # SELECT CHECKOUT ADDRESS
        # ==========================================
        elif action == "select_address":
            address_id = request.POST.get("address_id", "").strip()
            selected_address = get_addresses().filter(id=address_id).first()

            if selected_address:
                request.session["checkout_address_id"] = selected_address.id
                return redirect(request.path)

            context["errors"].append(
                "Please select a valid shipping address."
            )

        # ==========================================
        # SET AS DEFAULT ADDRESS
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
                "The address you want to set as default could not be found."
            )

        
        # ==========================================
        # PROCESS PAYMENT METHOD
        # ==========================================
        elif action == "select_payment":
            payment_method = request.POST.get(
                "payment_method", ""
            ).strip()

        
            bank = request.POST.get("bank", "").strip().lower()

            if payment_method not in allowed_payment_methods:
                context["errors"].append(
                    "Please select a valid payment method."
                )

            elif (
                payment_method == "bank_transfer"
                and bank not in allowed_banks
            ):
                context["errors"].append(
                    "Please select a bank for Virtual Account payment."
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
                        "Please provide the COD meeting location and time."
                    )
                else:
                    if timezone.is_naive(meeting_time):
                        meeting_time = timezone.make_aware(
                            meeting_time,
                            timezone.get_current_timezone(),
                        )

                    # Get the items to be purchased.
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
                            "Your cart is empty."
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
                                        f"COD - Campus meeting: "
                                        f"{meeting_location}"
                                    ),
                                    payment_status="pending",
                                    transaction_status="pending",
                                )

                                snapshot_review_sellers(order, order_items)

                                # Clear the cart only if
                                # checkout was initiated from the cart.
                                if not selected_item:
                                    CartItem.objects.filter(
                                        user=request.user
                                    ).delete()

                        except Exception as e:
                            print("ERROR CHECKOUT COD:", repr(e))
                            context["errors"].append(
                                f"Failed to create the order: {e}"
                            )
                        
                        else:
                            request.session.pop(
                                "checkout_payment_method", None
                            )
                            request.session.pop("checkout_bank", None)
                            request.session.pop("checkout_address_id", None)

                            messages.success(
                                request,
                                f"Order {order.order_id} has been created successfully! "
                                "Payment will be made when you meet the seller."
                            )

                            return redirect(
                                "transactions:checkout_success",
                                order_id=order.order_id,
                            )

            
            
            else:
                # Create a temporary order in the database for the QRIS/VA preview.
                # Do not create a Midtrans payment yet.

                request.session["checkout_payment_method"] = payment_method

                if payment_method == "bank_transfer":
                    request.session["checkout_bank"] = bank
                else:
                    request.session.pop("checkout_bank", None)

                request.session.modified = True

                selected_address = get_selected_address()

                if not selected_address:
                    context["errors"].append(
                        "Please add a shipping address before proceeding."
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
                            "Your cart is empty."
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
                                "The payment total is invalid."
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
                                    snapshot_review_sellers(order, order_items)

                            except Exception as e:
                                print("ERROR CHECKOUT:", repr(e))
                                context["errors"].append(
                                    "Failed to save the order. Please check the Django terminal for details."
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
                                    print("Error type:", type(e).__name__)
                                    print(
                                        "Message:",
                                        getattr(e, "message", None) or str(e)
                                    )
                                    print(
                                        "HTTP status:",
                                        getattr(e, "http_status_code", None)
                                    )
                                    print(
                                        "API response:",
                                        getattr(e, "api_response_dict", None)
                                    )
                                    print("====================================\n")

                                    context["errors"].append(
                                        "Midtrans could not create the payment. "
                                        "Your cart has not been cleared. "
                                        "Please check the Django terminal for details."
                                    )

                                else:
                                    # Clear the cart only if Midtrans successfully
                                    # accepts the payment creation request.
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

                                    messages.success(
                                        request,
                                        f"Order {order.order_id} has been created successfully! "
                                        "Please proceed with your payment."
                                    )

                                    return redirect(
                                        f"{preview_url}?{query_string}"
                                    )



    # ==========================================
    # DATA FOR THE TEMPLATE
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

    # Format the amount for direct purchases and cart purchases.
    context["total_display"] = (
        f"{context['total']:,.0f}".replace(",", ".")
    )

    return render(request, "transactions/checkout.html", context)



@login_required
def checkout_success(request, order_id):
    order = get_object_or_404(
        Transaction,
        order_id=order_id,
        buyer=request.user,
        payment_method="cod",
    )

    order.total_amount_display = (
        f"{order.total_amount:,.0f}".replace(",", ".")
    )

    return render(
        request,
        "transactions/checkout_success.html",
        {"order": order},
    )


@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(
        Transaction,
        order_id=order_id,
        buyer=request.user,
    )

    # Only pending orders can be cancelled.
    if (
        order.transaction_status != "pending"
        or order.payment_status != "pending"
    ):
        messages.error(
            request,
            "This order can no longer be cancelled.",
        )
        return redirect("transactions:transaction_history")

    # COD does not use Midtrans, so only the database needs to be updated.
    if order.payment_method == "cod":
        order.transaction_status = "cancelled"
        order.save(
            update_fields=["transaction_status", "updated_at"]
        )
        messages.success(
            request,
            f"Order {order.order_id} has been cancelled successfully."
        )
        return redirect("transactions:transaction_history")

    # Payment methods connected to Midtrans.
    if order.payment_method not in {"qris", "va"}:
        messages.error(
            request,
            "This payment method does not support cancellation yet.",
        )
        return redirect("transactions:transaction_history")

    try:
        if (
            not settings.MIDTRANS_SERVER_KEY
            or not settings.MIDTRANS_CLIENT_KEY
        ):
            raise ValueError(
                "Midtrans API key configuration is incomplete."
            )

        core_api = midtransclient.CoreApi(
            is_production=False,
            server_key=settings.MIDTRANS_SERVER_KEY,
            client_key=settings.MIDTRANS_CLIENT_KEY,
        )

        # Check the actual transaction status in Midtrans.
        status_response = core_api.transactions.status(order.order_id)
        midtrans_status = (
            status_response.get("transaction_status") or ""
        ).lower()

        # The transaction is still awaiting payment, so ask Midtrans
        # to cancel it first.
        if midtrans_status == "pending":
            cancel_response = core_api.transactions.cancel(order.order_id)
            cancel_status = (
                cancel_response.get("transaction_status") or ""
            ).lower()
            status_code = str(cancel_response.get("status_code", ""))

            if cancel_status != "cancel" and status_code != "200":
                messages.error(
                    request,
                    "Midtrans has not confirmed the cancellation. "
                    "The order status has not been changed.",
                )
                return redirect("transactions:transaction_history")

            order.transaction_status = "cancelled"
            order.payment_status = "failed"
            order.save(
                update_fields=[
                    "transaction_status",
                    "payment_status",
                    "updated_at",
                ]
            )
            messages.success(
                request,
                f"Order {order.order_id} has been cancelled successfully.",
            )

        # Midtrans has already marked the transaction as cancelled, expired,
        # denied, or failed. Synchronize the local status.
        elif midtrans_status in {"cancel", "expire", "deny", "failure"}:
            order.transaction_status = "cancelled"
            order.payment_status = (
                "expired" if midtrans_status == "expire" else "failed"
            )
            order.save(
                update_fields=[
                    "transaction_status",
                    "payment_status",
                    "updated_at",
                ]
            )
            messages.info(
                request,
                "The Midtrans transaction status is already "
                f"{midtrans_status}. The order status has been synchronized.",
            )

        # If it has already been paid, do not mark it as cancelled.
        elif midtrans_status in {"settlement", "capture"}:
            order.payment_status = "paid"
            order.transaction_status = "completed"
            order.save(
                update_fields=[
                    "payment_status",
                    "transaction_status",
                    "updated_at",
                ]
            )
            messages.info(
                request,
                "This transaction has already been paid. "
                "The order has been marked as completed.",
            )

        else:
            messages.error(
                request,
                "The current Midtrans transaction status "
                f"({midtrans_status or 'unknown'}) "
                "cannot be cancelled automatically yet.",
            )

    except Exception as e:
        print("ERROR CANCEL MIDTRANS:", repr(e))

        response_data = getattr(e, "api_response_dict", None)
        if not isinstance(response_data, dict):
            response_data = {}

        error_code = str(
            response_data.get("status_code")
            or getattr(e, "http_status_code", "")
        )
        if not error_code and "API status code: `404`" in str(e):
            error_code = "404"

        # A local order may sometimes be saved before the Midtrans transaction
        # is successfully created. If Midtrans returns 404 and no
        # transaction ID has been stored, cancel only the local order.
        if error_code == "404" and not order.midtrans_transaction_id:
            order.transaction_status = "cancelled"
            order.payment_status = "failed"
            order.save(
                update_fields=[
                    "transaction_status",
                    "payment_status",
                    "updated_at",
                ]
            )
            messages.success(
                request,
                f"Order {order.order_id} has been cancelled successfully. "
                "The payment transaction was not found in Midtrans.",
            )
        else:
            messages.error(
                request,
                "Failed to verify the cancellation with Midtrans. "
                "The order status has not been changed.",
            )

    return redirect("transactions:transaction_history")


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

    # Synchronize pending online payments with Midtrans.
    pending_orders = Transaction.objects.filter(
        buyer=request.user,
        payment_status="pending",
        transaction_status="pending",
        payment_method__in=["qris", "va"],
    ).order_by("-created_at")[:10]

    for pending_order in pending_orders:
        sync_midtrans_status(pending_order)

        # Determine whether the user is viewing purchased or sold orders.
    active_type = request.GET.get("type", "bought")

    if active_type not in {"sold", "bought"}:
        active_type = "bought"

    active_status = request.GET.get("status", "all")

    # Synchronize pending online payments before displaying orders.
    if active_type == "sold":
        pending_orders = Transaction.objects.filter(
            review_items__seller=request.user,
            payment_status="pending",
            transaction_status="pending",
            payment_method__in=["qris", "va"],
        ).distinct().order_by("-created_at")[:10]
    else:
        pending_orders = Transaction.objects.filter(
            buyer=request.user,
            payment_status="pending",
            transaction_status="pending",
            payment_method__in=["qris", "va"],
        ).order_by("-created_at")[:10]

    for pending_order in pending_orders:
        sync_midtrans_status(pending_order)

    # Retrieve orders based on the selected transaction type.
    if active_type == "sold":
        transactions = Transaction.objects.filter(
            review_items__seller=request.user
        ).distinct().order_by("-created_at")
    else:
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

    from account_profile.models import Review
    reviewed_ids = set(Review.objects.filter(reviewer=request.user).values_list('transaction_id', flat=True))
    for order in transactions:
        order.review_submitted = order.pk in reviewed_ids
        order.can_review = (order.transaction_status == 'completed' and not order.review_submitted
                            and order.buyer_id == request.user.pk
                            and order.review_items.exclude(seller_id=request.user.pk).filter(seller__isnull=False).exists())
    
    # Prepare product images for transaction history cards.
    history_transactions = list(transactions)

    # Find product names that may match the transaction.
    product_names = set()

    for transaction in history_transactions:
        item_name = (transaction.item_name or "").strip()

        if item_name:
            product_names.add(item_name)

            # If a transaction contains multiple products,
            # use the first product name as a fallback.
            if ", " in item_name:
                product_names.add(item_name.split(", ", 1)[0].strip())

    # Retrieve products together with their additional images.
    products_by_title = {}

    if product_names:
        products = Item.objects.filter(
            title__in=product_names
        ).prefetch_related("images").order_by("pk")

        for item in products:
            products_by_title.setdefault(item.title, item)

    # Match products and format prices for each transaction.
    for transaction in history_transactions:
        item_name = (transaction.item_name or "").strip()

        transaction.history_item = products_by_title.get(item_name)

        if transaction.history_item is None and ", " in item_name:
            first_item_name = item_name.split(", ", 1)[0].strip()
            transaction.history_item = products_by_title.get(first_item_name)

        transaction.total_amount_display = (
            f"{transaction.total_amount:,.0f}".replace(",", ".")
        )

    transactions = history_transactions


    return render(
        request,
        "transactions/transaction_history.html",
        {
            "transactions": transactions,
            "name": "Yelloved",
            "active_status": active_status,
            "active_type": active_type,
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
    wants_json = 'application/json' in request.headers.get('Accept', '')
    if request.method != "POST":
        if wants_json:
            return JsonResponse({'error': 'Use POST to add an item to your cart.'}, status=405)
        return redirect("items:explore_items")

    try:
        item = get_object_or_404(
            Item, pk=item_id, status=Item.Status.AVAILABLE,
            listing_type=Item.ListingType.SALE,
        )
    except Http404:
        if wants_json:
            return JsonResponse({'error': 'This item is no longer available to add to your cart.'}, status=404)
        raise

    if item.owner_id == request.user.id:
        if wants_json:
            return JsonResponse({'error': 'You cannot add your own item to the cart.'}, status=403)
        messages.error(request, "You cannot purchase your own item.")
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
        if not wants_json:
            messages.info(request, "This item is already in your cart.")
    elif not wants_json:
        messages.success(request, "Item added to your cart.")
    if wants_json:
        return JsonResponse({
            'created': created,
            'message': 'Added to your cart' if created else 'This item is already in your cart',
            'cart_count': CartItem.objects.filter(user=request.user).count(),
        })
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

    
    if order:
        sync_midtrans_status(order)

        # Do not allow payment instructions to be opened
        # if the order is no longer pending.
        if (
            order.payment_status != "pending"
            or order.transaction_status != "pending"
        ):
            if order.payment_status == "paid":
                messages.info(
                    request,
                    f"Order {order.order_id} has already been paid."
                )
            elif (
                order.payment_status in {"failed", "expired"}
                or order.transaction_status == "cancelled"
            ):
                messages.error(
                    request,
                    "This order has failed, expired, "
                    "or been cancelled. Please create a new order "
                    "to make another purchase."
                )
            else:
                messages.info(
                    request,
                    "This order is no longer awaiting payment."
                )

            return redirect("transactions:transaction_history")

        order.total_amount_display = (
            f"{order.total_amount:,.0f}".replace(",", ".")
        )

        # Retrieve the actual product image for the payment summary.
    review_item = (
        order.review_items
        .select_related("item")
        .filter(item__isnull=False)
        .first()
    )

    payment_item = review_item.item if review_item else None

    # Fallback for older transactions without purchase provenance.
    if payment_item is None:
        item_name = (order.item_name or "").strip()
        payment_item = Item.objects.filter(title=item_name).first()

        if payment_item is None and ", " in item_name:
            first_item_name = item_name.split(", ", 1)[0].strip()
            payment_item = Item.objects.filter(
                title=first_item_name
            ).first()

    order.payment_item = payment_item

        
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
    Create a payment transaction through the Midtrans Core API.
    Use Sandbox credentials only during testing.
    """

    if not settings.MIDTRANS_SERVER_KEY or not settings.MIDTRANS_CLIENT_KEY:
        raise ValueError(
            "Midtrans API key configuration is incomplete."
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
                "This Virtual Account bank is not supported."
            )

    else:
        raise ValueError(
            "Invalid payment method."
        )

    # Send the payment request to Midtrans.
    response = core_api.charge(params)

    # Save the transaction ID from Midtrans.
    order.midtrans_transaction_id = (
        response.get("transaction_id") or ""
    )

    # Save the expiry information if available.
    expiry_time = response.get("expiry_time")

    if expiry_time:
        parsed_expiry = parse_datetime(expiry_time)

        if parsed_expiry and timezone.is_naive(parsed_expiry):
            parsed_expiry = timezone.make_aware(parsed_expiry)

        order.midtrans_expiry_time = parsed_expiry

    # Save the QR code URL if it is provided in the response.
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

    # Save the Virtual Account details.
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

def apply_midtrans_status(order, data):
    """
    Apply a verified Midtrans transaction status to a local order.
    """

    # Verify the order ID.
    if data.get("order_id") != order.order_id:
        raise ValueError("Midtrans order ID mismatch.")

    # Verify the transaction amount.
    try:
        notified_amount = Decimal(str(data["gross_amount"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid Midtrans transaction amount.")

    if notified_amount != order.total_amount:
        raise ValueError("Midtrans transaction amount mismatch.")

    status = (data.get("transaction_status") or "").lower()
    fraud_status = (data.get("fraud_status") or "").lower()

    update_fields = {"updated_at"}

    # Save the Midtrans transaction ID.
    transaction_id = data.get("transaction_id")

    if transaction_id:
        order.midtrans_transaction_id = transaction_id
        update_fields.add("midtrans_transaction_id")

    # Successful payment.
    if (
        (status == "settlement" and fraud_status in {"", "accept"})
        or (status == "capture" and fraud_status == "accept")
    ):
        order.payment_status = "paid"
        order.transaction_status = "completed"

        update_fields.update({
            "payment_status",
            "transaction_status",
        })

    # Expired payment.
    elif status == "expire":
        if (
            order.payment_status != "paid"
            and order.transaction_status != "completed"
        ):
            order.payment_status = "expired"
            order.transaction_status = "cancelled"

            update_fields.update({
                "payment_status",
                "transaction_status",
            })

    # Cancelled or failed payment.
    elif status in {"cancel", "deny", "failure"}:
        if (
            order.payment_status != "paid"
            and order.transaction_status != "completed"
        ):
            order.payment_status = "failed"
            order.transaction_status = "cancelled"

            update_fields.update({
                "payment_status",
                "transaction_status",
            })

    order.save(update_fields=list(update_fields))


def sync_midtrans_status(order):
    """
    Retrieve the latest payment status directly from Midtrans.
    """

    # Only synchronize QRIS and Virtual Account transactions.
    if order.payment_method not in {"qris", "va"}:
        return

    # Only check transactions that are still pending.
    if order.payment_status != "pending":
        return

    if order.transaction_status != "pending":
        return

    if (
        not settings.MIDTRANS_SERVER_KEY
        or not settings.MIDTRANS_CLIENT_KEY
    ):
        return

    try:
        core_api = midtransclient.CoreApi(
            is_production=False,
            server_key=settings.MIDTRANS_SERVER_KEY,
            client_key=settings.MIDTRANS_CLIENT_KEY,
        )

        response = core_api.transactions.status(order.order_id)

        apply_midtrans_status(order, response)

    except Exception as e:
        print("ERROR SYNC MIDTRANS STATUS:", repr(e))


def snapshot_review_sellers(order, entries):
    TransactionItem.objects.bulk_create([
        TransactionItem(transaction=order, item=entry['item'], seller_id=entry['item'].owner_id)
        for entry in entries
    ])
@csrf_exempt
@require_POST
def midtrans_notification(request):
    """
    Receive payment notifications from Midtrans,
    verify the transaction status, and then update
    the order status in the Yelloved database.
    """

    # Read the notification payload.
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    order_id = payload.get("order_id")

    if not order_id:
        return JsonResponse(
            {"error": "Missing order_id"},
            status=400,
        )

    if not settings.MIDTRANS_SERVER_KEY or not settings.MIDTRANS_CLIENT_KEY:
        return JsonResponse(
            {"error": "Midtrans is not configured"},
            status=500,
        )

    # Ask the Midtrans SDK to verify the notification
    # and retrieve the verified transaction status.
    try:
        core_api = midtransclient.CoreApi(
            is_production=False,
            server_key=settings.MIDTRANS_SERVER_KEY,
            client_key=settings.MIDTRANS_CLIENT_KEY,
        )

        verified = core_api.transactions.notification(payload)

    except Exception as e:
        print("ERROR MIDTRANS NOTIFICATION:", repr(e))
        return JsonResponse(
            {"error": "Unable to verify Midtrans notification"},
            status=500,
        )

    if verified.get("order_id") != order_id:
        return JsonResponse(
            {"error": "Order ID mismatch"},
            status=400,
        )

    # Find the order registered in Yelloved.
    try:
        order = Transaction.objects.get(order_id=order_id)
    except Transaction.DoesNotExist:
        return JsonResponse(
            {"error": "Order not found"},
            status=404,
        )

    # Make sure the amount from the verified transaction
    # matches the amount of the local order.
    try:
        notified_amount = Decimal(str(verified["gross_amount"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid transaction amount"},
            status=400,
        )

    if notified_amount != order.total_amount:
        return JsonResponse(
            {"error": "Transaction amount mismatch"},
            status=400,
        )

     #Midtrans payment.
    apply_midtrans_status(order, verified)

    return JsonResponse({"status": "ok"}, status=200)

    return JsonResponse({"status": "ok"}, status=200)
