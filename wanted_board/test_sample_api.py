import copy
import json
from unittest.mock import Mock, patch

import requests
from django.core.cache import caches
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import sample_data as samples


TEST_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'wanted_samples': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'wanted-api-tests'},
}


def payload():
    return json.loads(samples.SNAPSHOT_PATH.read_text(encoding='utf-8'))


def api_response(data=None, status=200):
    response = Mock(status_code=status)
    response.json.return_value = payload() if data is None else data
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError('API down')
    return response


@override_settings(CACHES=TEST_CACHES)
class SampleAPITests(SimpleTestCase):
    def setUp(self):
        self.cache = caches['wanted_samples']
        self.cache.clear()
        self.addCleanup(self.cache.clear)

    @patch('wanted_board.sample_data.requests.get')
    def test_fetches_30_products_and_reuses_ten_minute_cache(self, get):
        data = payload()
        data['products'][0]['title'] = 'Live API study item'
        data['products'][0]['meta'] = {'createdAt': '2026-10-29T00:00:00Z'}
        data['products'][0].pop('createdAt', None)
        get.return_value = api_response(data)
        with patch.object(self.cache, 'set', wraps=self.cache.set) as write:
            first = samples.refresh_sample_wanted_posts()
        self.assertEqual(len(first), 30)
        self.assertEqual(first[0]['title'], 'Live API study item')
        self.assertEqual(first[0]['posted_on'], '29 October 2026')
        self.assertEqual(samples.refresh_sample_wanted_posts(), first)
        get.assert_called_once_with(samples.DUMMYJSON_PRODUCTS_URL, timeout=(2, 3), allow_redirects=False)
        self.assertIn(600, [call.kwargs['timeout'] for call in write.call_args_list])
        self.assertIn(86400, [call.kwargs['timeout'] for call in write.call_args_list])
        get.return_value.close.assert_called_once()

    @patch('wanted_board.sample_data.requests.get')
    def test_expired_fresh_cache_triggers_refresh(self, get):
        get.return_value = api_response()
        samples.refresh_sample_wanted_posts()
        self.cache.delete(samples.CACHE_KEY)
        data = payload()
        data['products'][0]['title'] = 'Refreshed item'
        get.return_value = api_response(data)
        self.assertEqual(samples.refresh_sample_wanted_posts()[0]['title'], 'Refreshed item')
        self.assertEqual(get.call_count, 2)

    @patch('wanted_board.sample_data.requests.get')
    def test_timeout_uses_last_good_result(self, get):
        data = payload()
        data['products'][0]['title'] = 'Last successful response'
        get.return_value = api_response(data)
        saved = samples.refresh_sample_wanted_posts()
        self.cache.delete(samples.CACHE_KEY)
        get.side_effect = requests.Timeout('Too slow')
        self.assertEqual(samples.refresh_sample_wanted_posts(), saved)
        self.assertEqual(samples.refresh_sample_wanted_posts(), saved)
        self.assertEqual(get.call_count, 2)

    @patch('wanted_board.sample_data.requests.get', side_effect=requests.ConnectionError('Offline'))
    def test_cold_outage_uses_snapshot_and_short_retry_cache(self, get):
        with patch.object(self.cache, 'set', wraps=self.cache.set) as write:
            result = samples.refresh_sample_wanted_posts()
        self.assertEqual(result, samples.SAMPLE_WANTED_POSTS)
        self.assertEqual(write.call_args.kwargs['timeout'], 60)
        samples.refresh_sample_wanted_posts()
        self.assertEqual(get.call_count, 1)
        self.assertIsNone(self.cache.get(samples.STALE_KEY))

    @patch('wanted_board.sample_data.requests.get')
    def test_api_recovers_after_fallback_expires(self, get):
        get.side_effect = [requests.Timeout(), api_response()]
        samples.refresh_sample_wanted_posts()
        self.cache.delete(samples.CACHE_KEY)
        samples.refresh_sample_wanted_posts()
        self.assertIsNotNone(self.cache.get(samples.STALE_KEY))
        self.assertEqual(get.call_count, 2)

    @patch('wanted_board.sample_data.requests.get')
    def test_bad_status_or_json_falls_back(self, get):
        broken_json = api_response()
        broken_json.json.side_effect = ValueError('Invalid JSON')
        for response in (api_response(status=503), api_response(status=302), broken_json):
            with self.subTest(status=response.status_code):
                self.cache.clear()
                get.return_value = response
                self.assertEqual(samples.refresh_sample_wanted_posts(), samples.SAMPLE_WANTED_POSTS)
                response.close.assert_called_once()

    @patch('wanted_board.sample_data.requests.get')
    def test_malformed_products_never_replace_last_good_data(self, get):
        data = payload()
        mutations = [('title', None), ('description', []), ('price', 'NaN'), ('price', None),
                     ('meta', 'invalid'), ('brand', 123), ('id', True)]
        bad_payloads = [{}, {'products': data['products'][:29]}, ['invalid']]
        for field, value in mutations:
            broken = copy.deepcopy(data)
            broken['products'][0][field] = value
            bad_payloads.append(broken)
        duplicate = copy.deepcopy(data)
        duplicate['products'][1]['id'] = duplicate['products'][0]['id']
        bad_payloads.append(duplicate)
        for broken in bad_payloads:
            with self.subTest(payload=type(broken).__name__):
                self.cache.clear()
                self.cache.set(samples.STALE_KEY, samples.SAMPLE_WANTED_POSTS)
                get.return_value = api_response(broken)
                self.assertEqual(samples.refresh_sample_wanted_posts(), samples.SAMPLE_WANTED_POSTS)
                self.assertEqual(self.cache.get(samples.STALE_KEY), samples.SAMPLE_WANTED_POSTS)

    @patch('wanted_board.sample_data.requests.get')
    def test_cache_disk_failure_does_not_break_api_result(self, get):
        get.return_value = api_response()
        with patch.object(self.cache, 'get', side_effect=OSError('No cache disk')), \
                patch.object(self.cache, 'set', side_effect=OSError('No cache disk')):
            self.assertEqual(len(samples.refresh_sample_wanted_posts()), 30)


class SampleAPIViewTests(TestCase):
    @patch('wanted_board.sample_data.requests.get')
    def test_pages_never_fetch_dummyjson_even_with_empty_cache(self, get):
        cache = caches['wanted_samples']
        cache.clear()
        self.addCleanup(cache.clear)
        from django.contrib.auth import get_user_model
        from wanted_board.models import WantedPost
        owner = get_user_model().objects.create_user(username='stored-post-owner')
        WantedPost.objects.create(requester=owner, title='Stored database request', budget=50000)
        self.assertContains(self.client.get(reverse('wanted_board:show_wanted')), 'Stored database request')
        for url in (reverse('wanted_board:show_wanted'), reverse('show_main'),
                    reverse('items:explore_items')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        get.assert_not_called()
