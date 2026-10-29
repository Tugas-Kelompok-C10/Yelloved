from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import WantedPost
from .sample_data import SAMPLE_WANTED_POSTS
from .views import _wanted_cards, _wanted_page


class BudgetSortTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='budget-sort-owner')
        # More than one page, tied budgets, and legacy unspecified/zero budgets.
        WantedPost.objects.bulk_create([
            WantedPost(requester=self.owner, title=f'Book lamp {n}', description='Study item',
                       category='books' if n % 2 else 'electronics', budget=(n % 11) * 25000)
            for n in range(70)
        ] + [WantedPost(requester=self.owner, title='Flexible budget', budget=None)])
        self.posts = WantedPost.objects.select_related('requester').order_by('-created_at', '-pk')

    def test_budget_order_merges_real_and_demo_posts_before_paginating(self):
        for direction in ('budget_asc', 'budget_desc'):
            with self.subTest(direction=direction):
                expected = _wanted_cards(self.posts, SAMPLE_WANTED_POSTS)
                sign = 1 if direction == 'budget_asc' else -1
                expected.sort(key=lambda card: (card['budget'] is None, (card['budget'] or 0) * sign))
                actual = []
                for number in range(1, 10):
                    page = _wanted_page(self.posts, SAMPLE_WANTED_POSTS, number, sort=direction)
                    actual.extend(page.object_list)
                    if not page.has_next(): break
                self.assertEqual([row['detail_url'] for row in actual], [row['detail_url'] for row in expected])
                self.assertIsNone(actual[-1]['budget'])

    def test_sorted_page_uses_bounded_database_slice_without_n_plus_one(self):
        with self.assertNumQueries(2):
            page = _wanted_page(self.posts, SAMPLE_WANTED_POSTS, 5, sort='budget_asc')
        self.assertEqual(len(page.object_list), 12)

    @patch('wanted_board.views.get_sample_wanted_posts', return_value=SAMPLE_WANTED_POSTS)
    def test_sort_combines_with_category_query_and_pagination(self, _):
        url = reverse('wanted_board:show_wanted')
        for sort in ('budget_asc', 'budget_desc'):
            response = self.client.get(url, {'sort': sort, 'category': 'books', 'q': 'Book lamp'})
            self.assertEqual(response.context['selected_sort'], sort)
            rows = response.context['wanted_cards']
            self.assertTrue(rows)
            budgets = [row['budget'] for row in rows]
            self.assertEqual(budgets, sorted(budgets, reverse=sort == 'budget_desc'))
            for link in response.context['pagination_links']:
                if link['url']:
                    self.assertIn(f'sort={sort}', link['url'])
                    self.assertIn('category=books', link['url'])
                    self.assertIn('q=Book+lamp', link['url'])
            ajax = self.client.get(url, {'sort': sort, 'category': 'books', 'q': 'Book lamp', 'page': 2},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
            self.assertEqual(ajax['selected_sort'], sort)
            self.assertEqual(ajax['selected_category'], 'books')
            self.assertEqual(ajax['page_number'], 2)

    @patch('wanted_board.views.get_sample_wanted_posts', return_value=())
    def test_invalid_sort_falls_back_to_existing_newest_order(self, _):
        response = self.client.get(reverse('wanted_board:show_wanted'), {'sort': 'unexpected'})
        self.assertEqual(response.context['selected_sort'], '')
        expected = list(self.posts[:12].values_list('title', flat=True))
        self.assertEqual([card['title'] for card in response.context['wanted_cards']], expected)
