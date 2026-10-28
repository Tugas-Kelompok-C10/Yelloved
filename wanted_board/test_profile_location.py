from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from account_profile.models import Address
from .creation import issue_creation_token
from .forms import WantedPostForm
from .models import WantedPost


class WantedProfileLocationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="requester")
        self.client.force_login(self.user)

    def address(self, **changes):
        data = {"user": self.user, "label": "Campus", "recipient_name": "Student",
                "street_address": "Private street, house 42", "city": "Depok",
                "province": "West Java", "is_default": True}
        data.update(changes)
        return Address.objects.create(**data)

    def test_new_form_prefills_main_address_area_without_street(self):
        self.address(city="Jakarta", is_default=False, label="A different address")
        self.address()
        response = self.client.get(reverse("wanted_board:show_wanted"))
        form = response.context["creation_form"]
        self.assertEqual(form["location"].value(), "Depok, West Java")
        self.assertNotContains(response, "Private street, house 42")
        self.assertNotIn("image", form.fields)

    def test_missing_address_is_editable_and_empty(self):
        form = WantedPostForm(user=self.user)
        self.assertFalse(form["location"].value())
        self.assertFalse(form.fields["location"].disabled)

    def test_submitted_location_can_override_profile_and_survives_errors(self):
        self.address()
        payload = {"title": "Book", "description": "A course book", "category": "books",
                   "budget": "0", "location": "UI Library", "creation_token": issue_creation_token(self.user)}
        url = reverse("wanted_board:create_wanted")
        invalid = self.client.post(url, payload)
        self.assertEqual(invalid.context["creation_form"]["location"].value(), "UI Library")
        payload["budget"] = "80000"
        saved = self.client.post(url, payload, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(saved.status_code, 200)
        post = WantedPost.objects.get(requester=self.user)
        self.assertEqual(post.location, "UI Library")
        self.assertFalse(hasattr(post, "image"))

    def test_edit_keeps_post_location_when_profile_address_changes(self):
        address = self.address()
        post = WantedPost.objects.create(requester=self.user, title="Book", location="UI Library")
        address.city = "Bogor"
        address.save()
        form = WantedPostForm(instance=post, user=self.user)
        self.assertEqual(form["location"].value(), "UI Library")

    def test_long_profile_area_falls_back_to_city(self):
        self.address(city="D" * 100, province="P" * 100)
        self.assertEqual(WantedPostForm(user=self.user)["location"].value(), "D" * 100)
