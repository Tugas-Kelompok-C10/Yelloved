import json

from django.test import TestCase

from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from .forms import ProfileForm
from .models import Profile


class AccountFeedbackTests(TestCase):
    def test_public_profile_has_requested_banner_without_fake_stats(self):
        response = self.client.get(reverse("account_profile:user_profile", args=[self.user.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "public-profile-banner")
        self.assertContains(response, "Preloved things, new stories.")
        self.assertContains(response, "No reviews yet")
        self.assertNotContains(response, "A little care. A second life.")

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="profile-test", password="A-strong-test-password-16")
        self.profile = Profile.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.payload = {"first_name": "Cindy", "email": "cindy@example.com", "gender": "female", "phone_number": "08123456789", "date_of_birth": "2000-01-02"}

    def test_settings_pages_use_shared_account_styles_and_toaster(self):
        for route in ("profile", "address_list", "payment_methods", "notifications", "privacy_security", "reviews", "help_messages"):
            response = self.client.get(reverse(f"account_profile:{route}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "css/account.css")
            self.assertContains(response, "js/account.js")
            self.assertContains(response, 'id="site-toast-region"', count=1)

    def test_profile_save_uses_success_toast_and_keeps_date_value(self):
        response = self.client.post(reverse("account_profile:profile"), self.payload, follow=True)
        self.assertContains(response, "Your profile has been updated.")
        self.assertContains(response, "2000-01-02")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Cindy")

    def test_oversized_and_corrupt_photos_leave_profile_unchanged(self):
        for upload, expected in (
            (SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png"), "5 MB"),
            (SimpleUploadedFile("fake.png", b"\x89PNG\r\n\x1a\nnot-a-real-image", content_type="image/png"), "could not be read"),
        ):
            response = self.client.post(reverse("account_profile:profile"), {**self.payload, "photo": upload})
            self.assertContains(response, expected)
            self.user.refresh_from_db()
            self.profile.refresh_from_db()
            self.assertEqual(self.user.first_name, "")
            self.assertFalse(self.profile.photo)
            self.assertEqual(response.context["form"]["first_name"].value(), "Cindy")

    def test_photo_pixel_limit_and_valid_image(self):
        for dimensions, valid in (((4097, 1), False), ((32, 32), True)):
            data = BytesIO()
            Image.new("RGB", dimensions).save(data, format="PNG")
            upload = SimpleUploadedFile("photo.png", data.getvalue(), content_type="image/png")
            form = ProfileForm(self.payload, {"photo": upload}, instance=self.profile, user=self.user)
            self.assertEqual(form.is_valid(), valid)
            if not valid:
                self.assertIn("4096", form.errors["photo"][0])
            else:
                with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
                    profile = form.save()
                    self.assertTrue(profile.photo.storage.exists(profile.photo.name))

    def test_address_validation_keeps_add_form_visible(self):
        response = self.client.post(reverse("account_profile:address_list"), {"label": "Campus"})
        self.assertTrue(response.context["form"].errors)
        self.assertNotContains(response, 'id="address-form" hidden')

    def test_replacing_photo_removes_previous_file_and_keeps_new_file(self):
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            for name in ("first.png", "second.png"):
                data = BytesIO()
                Image.new("RGB", (20, 20)).save(data, format="PNG")
                form = ProfileForm(self.payload, {"photo": SimpleUploadedFile(name, data.getvalue(), content_type="image/png")},
                                   instance=self.profile, user=self.user)
                self.assertTrue(form.is_valid(), form.errors)
                self.profile = form.save()
                if name == "first.png":
                    previous = self.profile.photo.name
            self.assertFalse(self.profile.photo.storage.exists(previous))
            self.assertTrue(self.profile.photo.storage.exists(self.profile.photo.name))
            self.assertTrue(self.profile.photo.name.startswith("profile_photos/"))

    def test_missing_photo_still_renders_page_with_shared_fallback(self):
        self.profile.photo = "profile_photos/missing.png"
        self.profile.save()
        response = self.client.get(reverse("account_profile:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/media/profile_photos/missing.png')
        self.assertContains(response, 'js/media_fallback.js')
        self.assertContains(response, 'data-avatar-fallback="/static/img/Default_PP.png"')

    def test_empty_payment_and_password_are_also_rejected_on_server(self):
        from .models import PaymentMethod
        for route in ("payment_methods", "privacy_security"):
            response = self.client.post(reverse(f"account_profile:{route}"), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(PaymentMethod.objects.filter(user=self.user).exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-strong-test-password-16"))

    def test_auth_pages_and_login_feedback_are_english(self):
        self.client.logout()
        for route in ("login", "account_profile:register"):
            response = self.client.get(reverse(route))
            self.assertContains(response, "css/account.css")
        response = self.client.post(reverse("login"), {"username": self.user.username, "password": "A-strong-test-password-16", "next": reverse("account_profile:profile")}, follow=True)
        self.assertContains(response, "Welcome back to Yelloved!")

    def test_ajax_profile_and_preferences_return_feedback_without_redirect(self):
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.post(reverse("account_profile:profile"), self.payload, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], reverse("account_profile:profile"))
        self.assertIn("updated", response.json()["message"])
        response = self.client.post(reverse("account_profile:notifications"), {"promotions": "on"}, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], reverse("account_profile:notifications"))

    def test_ajax_address_actions_and_required_fields(self):
        from .models import Address
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        data = {"label": "Campus", "recipient_name": "QA", "phone_number": "08123456789",
                "street_address": "UI campus", "city": "Depok", "province": "West Java", "postal_code": "16424"}
        response = self.client.post(reverse("account_profile:address_list"), {**data, "province": ""}, **headers)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Address.objects.count(), 0)
        response = self.client.post(reverse("account_profile:address_list"), data, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("added", response.json()["message"])
        address = Address.objects.get(user=self.user)
        for route, payload in (("edit_address", {**data, "label": "Home"}), ("set_default_address", {}), ("delete_address", {})):
            response = self.client.post(reverse(f"account_profile:{route}", args=[address.pk]), payload, **headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["url"], reverse("account_profile:address_list"))

    def test_ajax_payment_actions_and_password_validation(self):
        from .models import PaymentMethod
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        data = {"method_type": "bank", "provider": "Demo bank", "account_name": "QA", "account_identifier": "12345678"}
        response = self.client.post(reverse("account_profile:payment_methods"), data, **headers)
        self.assertIn("added", response.json()["message"])
        method = PaymentMethod.objects.get(user=self.user)
        response = self.client.post(reverse("account_profile:edit_payment_method", args=[method.pk]), {**data, "provider": "Updated bank"}, **headers)
        self.assertIn("updated", response.json()["message"])
        response = self.client.post(reverse("account_profile:delete_payment_method", args=[method.pk]), {}, **headers)
        self.assertIn("deleted", response.json()["message"])
        response = self.client.post(reverse("account_profile:privacy_security"), {"old_password": "incorrect"}, **headers)
        self.assertTrue(response.context["form"].errors)
        response = self.client.post(reverse("account_profile:privacy_security"), {
            "old_password": "A-strong-test-password-16", "new_password1": "Another-test-password-2026", "new_password2": "Another-test-password-2026"}, **headers)
        self.assertEqual(response.json()["url"], reverse("account_profile:privacy_security"))
        self.assertEqual(self.client.get(reverse("account_profile:profile")).status_code, 200)


class AccountProfileApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-profile-test", password="A-strong-test-password-16", email="before@example.com")
        self.client.force_login(self.user)
        self.json_headers = {"content_type": "application/json"}

    def post_json(self, route, payload):
        return self.client.post(reverse(f"account_profile:{route}"), json.dumps(payload), **self.json_headers)

    def test_profile_api_reads_and_updates_user_and_profile_fields(self):
        from .models import Profile
        response = self.client.get(reverse("account_profile:api_profile"))
        self.assertEqual(response.status_code, 200)
        response = self.post_json("api_profile", {
            "first_name": "Updated", "email": "updated@example.com", "date_of_birth": "2001-02-03",
            "gender": "female", "phone_number": "+628123456789",
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(profile.phone_number, "+628123456789")

    def test_address_api_supports_create_read_update_default_and_delete(self):
        from .models import Address
        endpoint = reverse("account_profile:api_addresses")
        payload = {"label": "Home", "recipient_name": "API User", "phone_number": "08123456789",
                   "street_address": "Main street 1", "city": "Depok", "province": "West Java",
                   "postal_code": "16424", "is_default": True}
        response = self.client.post(endpoint, json.dumps(payload), **self.json_headers)
        self.assertEqual(response.status_code, 201, response.content)
        address_id = response.json()["id"]
        self.assertEqual(self.client.get(endpoint).json()["results"][0]["id"], address_id)
        response = self.client.patch(reverse("account_profile:api_address_detail", args=[address_id]),
                                     json.dumps({"city": "Bandung"}), **self.json_headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["city"], "Bandung")
        second = {**payload, "label": "Office", "is_default": False}
        second_response = self.client.post(endpoint, json.dumps(second), **self.json_headers)
        second_id = second_response.json()["id"]
        self.assertFalse(Address.objects.get(pk=second_id).is_default)
        response = self.client.post(reverse("account_profile:api_address_default", args=[second_id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Address.objects.get(pk=second_id).is_default)
        response = self.client.delete(reverse("account_profile:api_address_detail", args=[address_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Address.objects.filter(pk=address_id).exists())

    def test_payment_method_api_supports_create_read_update_and_delete(self):
        from .models import PaymentMethod
        endpoint = reverse("account_profile:api_payment_methods")
        payload = {"method_type": "bank", "provider": "Demo bank", "account_name": "API User",
                   "account_identifier": "123456789", "is_default": True}
        response = self.client.post(endpoint, json.dumps(payload), **self.json_headers)
        self.assertEqual(response.status_code, 201, response.content)
        method_id = response.json()["id"]
        self.assertEqual(self.client.get(endpoint).json()["results"][0]["id"], method_id)
        response = self.client.patch(reverse("account_profile:api_payment_method_detail", args=[method_id]),
                                     json.dumps({"provider": "Updated bank"}), **self.json_headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["provider"], "Updated bank")
        response = self.client.delete(reverse("account_profile:api_payment_method_detail", args=[method_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentMethod.objects.filter(pk=method_id).exists())

    def test_notification_preferences_and_password_are_updated_by_api(self):
        from .models import NotificationPreference
        prefs_url = reverse("account_profile:api_notifications")
        self.assertEqual(self.client.get(prefs_url).status_code, 200)
        response = self.client.patch(prefs_url, json.dumps({"order_updates": False, "promotions": True}), **self.json_headers)
        self.assertEqual(response.status_code, 200, response.content)
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(prefs.order_updates)
        self.assertTrue(prefs.promotions)
        response = self.post_json("api_change_password", {
            "old_password": "A-strong-test-password-16", "new_password1": "Another-strong-password-2026",
            "new_password2": "Another-strong-password-2026",
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-strong-password-2026"))

    def test_api_mutations_require_authentication_and_validate_owner(self):
        from .models import Address
        payload = {"label": "Home", "recipient_name": "Other", "phone_number": "08123456789",
                   "street_address": "Other street", "city": "Depok", "province": "West Java", "postal_code": "16424"}
        other = get_user_model().objects.create_user(username="other-api-user")
        address = Address.objects.create(user=other, **payload)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("account_profile:api_profile")).status_code, 401)
        self.client.force_login(self.user)
        response = self.client.delete(reverse("account_profile:api_address_detail", args=[address.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Address.objects.filter(pk=address.pk).exists())
