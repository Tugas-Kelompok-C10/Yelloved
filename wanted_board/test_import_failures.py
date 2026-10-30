from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from wanted_board.models import WantedPost
from wanted_board.sample_data import DUMMYJSON_PRODUCTS_URL
from wanted_board.test_sample_api import api_response


class DummyJSONWantedImportTests(TestCase):
    @patch('wanted_board.sample_data.requests.get')
    def test_success_uses_timeout_and_reimport_keeps_same_posts(self, get):
        get.return_value = api_response()
        call_command('import_dummyjson_wanted', stdout=StringIO())
        before = list(WantedPost.objects.order_by('pk').values())
        self.assertEqual(len(before), 30)
        call_command('import_dummyjson_wanted', stdout=StringIO())
        self.assertEqual(list(WantedPost.objects.order_by('pk').values()), before)
        get.assert_called_with(DUMMYJSON_PRODUCTS_URL, timeout=(2, 3), allow_redirects=False)

    def assert_failure_preserves_posts(self, failure):
        with patch('wanted_board.sample_data.requests.get') as get:
            get.return_value = api_response()
            call_command('import_dummyjson_wanted', stdout=StringIO())
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.create_user(username='real_student')
            WantedPost.objects.create(requester=user, title='My manual post',
                                      description='Keep me', budget=50000)
            before = list(WantedPost.objects.order_by('pk').values())
            get.side_effect = failure
            with self.assertRaisesMessage(CommandError, 'existing posts were not changed'):
                call_command('import_dummyjson_wanted', stdout=StringIO())
            self.assertEqual(list(WantedPost.objects.order_by('pk').values()), before)

    def test_timeout_preserves_imported_and_manual_posts(self):
        self.assert_failure_preserves_posts(requests.Timeout('Timed out'))

    def test_connection_error_preserves_imported_and_manual_posts(self):
        self.assert_failure_preserves_posts(requests.ConnectionError('Offline'))

    def test_request_exception_preserves_imported_and_manual_posts(self):
        self.assert_failure_preserves_posts(requests.RequestException('Request failed'))

    def test_command_line_reports_request_failures_without_traceback(self):
        from wanted_board.management.commands.import_dummyjson_wanted import Command
        for error in (requests.Timeout('Timed out'), requests.ConnectionError('Offline')):
            with self.subTest(error=type(error).__name__):
                stderr = StringIO()
                command = Command(stdout=StringIO(), stderr=stderr)
                with patch('wanted_board.sample_data.requests.get', side_effect=error), \
                        patch('django.core.management.base.connections.close_all'):
                    with self.assertRaises(SystemExit) as stopped:
                        command.run_from_argv(['manage.py', 'import_dummyjson_wanted'] + [])
                self.assertEqual(stopped.exception.code, 1)
                self.assertIn('existing posts were not changed', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
