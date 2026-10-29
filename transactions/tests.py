from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from .models import CartItem


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
