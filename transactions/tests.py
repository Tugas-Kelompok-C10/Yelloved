from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from .models import CartItem

from rest_framework import status
from rest_framework.test import APITestCase
from .models import Transaction


class CartRenderingTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(username="cart-buyer")
        self.seller = get_user_model().objects.create_user(username="cart-seller")
        self.client.force_login(self.buyer)
        self.url = reverse("transactions:cart")

    def test_empty_cart_renders(self):
        self.assertContains(self.client.get(self.url), "Your cart is empty")

    def test_populated_cart_renders_selection_and_preserves_checkout(self):
        item = Item.objects.create(owner=self.seller, title="Study lamp", category="home",
                                   condition="good", listing_type="sale", price=50000, location="UI")
        entry = CartItem.objects.create(user=self.buyer, item=item)
        response = self.client.get(self.url)
        self.assertContains(response, 'id="cart-selection-form"')
        self.assertContains(response, 'name="selected_items"')
        self.assertContains(response, item.title)
        self.assertContains(response, self.seller.username)
        response = self.client.post(self.url, {"selected_items": [entry.pk], "action": "checkout"})
        self.assertRedirects(response, reverse("transactions:checkout"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["checkout_cart_entry_ids"], [entry.pk])

class TransactionAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.buyer = User.objects.create_user(
            username="api-buyer",
            password="testpassword123"
        )

        self.other_buyer = User.objects.create_user(
            username="other-buyer",
            password="testpassword123"
        )

        self.url = reverse("transactions:transaction_api")

        self.transaction = Transaction.objects.create(
            order_id="TEST-ORDER-001",
            buyer=self.buyer,
            item_name="Vintage Denim Jacket",
            quantity=1,
            total_amount=150000,
            payment_method="qris",
            shipping_address="Depok, Indonesia",
        )

        Transaction.objects.create(
            order_id="TEST-ORDER-002",
            buyer=self.other_buyer,
            item_name="Canvas Tote Bag",
            quantity=1,
            total_amount=75000,
            payment_method="cod",
            shipping_address="Jakarta, Indonesia",
        )

    def test_unauthenticated_user_cannot_access_api(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_authenticated_user_can_access_api(self):
        self.client.force_authenticate(user=self.buyer)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_user_only_sees_own_transactions(self):
        self.client.force_authenticate(user=self.buyer)

        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["order_id"],
            "TEST-ORDER-001"
        )
