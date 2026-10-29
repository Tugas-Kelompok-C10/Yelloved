from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import WantedPost


@patch('wanted_board.views.get_sample_wanted_posts', return_value=())
class WantedHtmxTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username='htmx-owner')
        WantedPost.objects.bulk_create([
            WantedPost(requester=owner, title=f'Study book {number}',
                       category='books', budget=(number + 1) * 1000)
            for number in range(14)
        ])
        WantedPost.objects.create(requester=owner, title='Study lamp', category='electronics', budget=1000)
        self.url = reverse('wanted_board:show_wanted')

    def test_htmx_returns_only_results_and_combines_all_filters(self, _):
        response = self.client.get(self.url, {'q': 'Study', 'category': 'books',
                                             'sort': 'budget_asc', 'page': 2}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, '<form')
        self.assertContains(response, 'data-wanted-state')
        self.assertContains(response, 'data-category="books"')
        self.assertContains(response, 'Study book 12')
        self.assertNotContains(response, 'Study lamp')
        self.assertEqual([row['title'] for row in response.context['wanted_cards']], ['Study book 12', 'Study book 13'])
        for field in ('q=Study', 'category=books', 'sort=budget_asc', 'page=2'):
            self.assertIn(field, response.context['results_url'])
        self.assertIn('HX-Request', response.headers['Vary'])

    def test_full_page_and_legacy_json_are_still_supported(self, _):
        page = self.client.get(self.url)
        self.assertContains(page, 'input changed delay:300ms')
        self.assertContains(page, 'hx-sync="this:replace"')
        self.assertContains(page, 'id="wanted-results"')
        self.assertContains(page, 'htmx-2.0.11.min.js')
        self.assertIn('HX-Request', page.headers['Vary'])
        data = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
        self.assertIn('html', data)
        self.assertIn('pagination_html', data)

    def test_htmx_escapes_query_and_post_content(self, _):
        payload = '<img src=x onerror=alert(1)>'
        WantedPost.objects.create(requester=get_user_model().objects.first(), title=payload,
                                  location=payload, category='other', budget=1000)
        response = self.client.get(self.url, {'category': 'other'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, '&lt;img src=x onerror=alert(1)&gt;')
        self.assertNotContains(response, payload)
