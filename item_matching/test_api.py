from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from items.models import Item
from wanted_board.models import WantedPost

from .models import ItemOffer, ItemRequest
from .tests import Base, make_item, make_post


class ItemMatchingApiTests(Base, APITestCase):
    def setUp(self):
        super().setUp()
        self.item = make_item(self.owner)
        self.post = make_post(self.buyer)

    def test_requires_authentication(self):
        for url in (reverse("item_matching:dashboard_api"),
                    reverse("item_matching:item_suggestions_api", args=[self.item.pk])):
            self.assertIn(self.client.get(url).status_code, (401, 403))

    def test_token_authentication_works(self):
        token = Token.objects.create(user=self.owner)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(reverse("item_matching:dashboard_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"tab": "incoming", "results": []})

    def test_dashboard_rejects_unknown_tab(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(reverse("item_matching:dashboard_api"), {"tab": "nope"})
        self.assertEqual(response.status_code, 400)

    def test_create_request_and_duplicate_blocked(self):
        self.client.force_authenticate(self.buyer)
        url = reverse("item_matching:request_create_api", args=[self.item.pk])
        response = self.client.post(url, {"offer_price": "45000", "message": "mau"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")
        self.assertIsNone(response.json()["contact"])
        again = self.client.post(url, {"offer_price": "40000"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(ItemRequest.objects.count(), 1)

    def test_cannot_request_own_item(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("item_matching:request_create_api", args=[self.item.pk]), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ItemRequest.objects.exists())

    def test_accept_request_only_by_item_owner(self):
        req = ItemRequest.objects.create(item=self.item, requester=self.buyer, offer_price=45000)
        url = reverse("item_matching:request_accept_api", args=[req.pk])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(url).status_code, 409)
        self.client.force_authenticate(self.owner)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.UNAVAILABLE)

    def test_cancel_request_by_requester(self):
        req = ItemRequest.objects.create(item=self.item, requester=self.buyer, offer_price=45000)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(reverse("item_matching:request_cancel_api", args=[req.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")

    def test_missing_object_returns_404(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(reverse("item_matching:request_accept_api", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_create_offer_and_accept_matches_post(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("item_matching:offer_create_api", args=[self.post.pk]),
            {"item": self.item.pk, "message": "ada"}, format="json")
        self.assertEqual(response.status_code, 201)
        offer = ItemOffer.objects.get()
        self.client.force_authenticate(self.buyer)
        accepted = self.client.post(reverse("item_matching:offer_accept_api", args=[offer.pk]))
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertIsNone(accepted.json()["contact"])  # no phone number on the profile
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, WantedPost.Status.MATCHED)

    def test_photo_offer_without_item_is_listed(self):
        ItemOffer.objects.create(wanted_post=self.post, offerer=self.owner, offered_price=45000,
                                 message="Foto lampu belajar")
        self.client.force_authenticate(self.buyer)
        response = self.client.get(reverse("item_matching:dashboard_api"), {"tab": "offers_received"})
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertIsNone(row["item"])
        self.assertEqual(row["title"], self.post.title)
        self.assertEqual(row["price_display"], "Rp45.000")

    def test_suggestions_are_owner_only(self):
        item_url = reverse("item_matching:item_suggestions_api", args=[self.item.pk])
        wanted_url = reverse("item_matching:wanted_suggestions_api", args=[self.post.pk])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(item_url).status_code, 403)
        self.assertEqual(self.client.get(wanted_url).status_code, 403)
        self.client.force_authenticate(self.owner)
        response = self.client.get(item_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["wanted_id"], str(self.post.pk))
