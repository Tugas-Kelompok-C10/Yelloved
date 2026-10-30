from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .creation import issue_creation_token
from .forms import WantedPostForm
from .models import WantedPost

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class WantedInputLimitTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="limits-owner")
        self.client.force_login(self.user)
        self.data = {"title": "Lamp", "description": "a" * 500, "category": "home", "budget": 10000}

    def test_description_boundary_in_form_and_model(self):
        self.assertTrue(WantedPostForm(self.data).is_valid())
        form = WantedPostForm({**self.data, "description": "a" * 501})
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)
        self.assertEqual(WantedPost._meta.get_field("description").max_length, 500)
        self.assertIn('maxlength="500"', str(form["description"]))

    def test_oversized_create_and_edit_are_rejected_even_without_browser_validation(self):
        token = issue_creation_token(self.user)
        response = self.client.post(reverse("wanted_board:create_wanted"), {
            **self.data, "description": "a" * 501, "creation_token": token,
        }, **AJAX)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(WantedPost.objects.exists())
        post = WantedPost.objects.create(requester=self.user, **self.data)
        response = self.client.post(reverse("wanted_board:edit_wanted", args=[post.pk]), {
            **self.data, "description": "b" * 501, "revision": post.updated_at.isoformat(),
        }, **AJAX)
        self.assertEqual(response.status_code, 422)
        post.refresh_from_db()
        self.assertEqual(post.description, "a" * 500)

    def test_board_limits_search_query_and_preserves_bounded_pagination_urls(self):
        query = "a" * 70
        WantedPost.objects.create(requester=self.user, title="Match", description=query, budget=10000)
        for headers in ({}, AJAX):
            response = self.client.get(reverse("wanted_board:show_wanted"), {"q": query + "ignored", "page": 2}, **headers)
            self.assertEqual(response.status_code, 200)
            if headers:
                self.assertIn("Match", response.json()["html"])
            else:
                self.assertEqual(response.context["query"], query)
                self.assertContains(response, 'maxlength="70"')
                self.assertNotContains(response, query + "ignored")
