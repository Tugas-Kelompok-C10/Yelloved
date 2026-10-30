from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from items.models import Item


class DummyJSONImportFailureTests(TestCase):
    def products(self):
        return {'products': [dict(id=n, title=f'Shirt {n}', category='mens-shirts', price=10)
                             for n in range(1, 51)]}

    @patch('items.management.commands.import_dummyjson_items.requests.get')
    def test_success_uses_timeout_and_reimport_keeps_same_rows(self, get):
        get.return_value.json.return_value = self.products()
        call_command('import_dummyjson_items', limit=50, stdout=StringIO())
        before = list(Item.objects.order_by('pk').values())
        call_command('import_dummyjson_items', limit=50, stdout=StringIO())
        self.assertEqual(list(Item.objects.order_by('pk').values()), before)
        self.assertEqual(Item.objects.filter(external_id__range=(1, 50)).count(), 50)
        for call in get.call_args_list:
            self.assertGreater(call.kwargs['timeout'], 0)
        get.return_value.raise_for_status.assert_called()

    def assert_failed_refresh_preserves_rows(self, failure):
        with patch('items.management.commands.import_dummyjson_items.requests.get') as get:
            get.return_value.json.return_value = self.products()
            call_command('import_dummyjson_items', limit=50, stdout=StringIO())
            Item.objects.create(title='Manual item', description='Keep me', price=5000,
                                location='Depok', source='user')
            before = list(Item.objects.order_by('pk').values())
            get.side_effect = failure
            with self.assertRaisesMessage(CommandError, 'Gagal mengambil DummyJSON'):
                call_command('import_dummyjson_items', limit=50, refresh=True, stdout=StringIO())
            self.assertEqual(list(Item.objects.order_by('pk').values()), before)

    def test_timeout_preserves_existing_imported_and_manual_items(self):
        self.assert_failed_refresh_preserves_rows(requests.Timeout('Timed out'))

    def test_connection_error_preserves_existing_imported_and_manual_items(self):
        self.assert_failed_refresh_preserves_rows(requests.ConnectionError('Offline'))

    def test_request_exception_preserves_existing_imported_and_manual_items(self):
        self.assert_failed_refresh_preserves_rows(requests.RequestException('Request failed'))

    def test_command_line_reports_request_failures_without_traceback(self):
        from items.management.commands.import_dummyjson_items import Command
        for error in (requests.Timeout('Timed out'), requests.ConnectionError('Offline')):
            with self.subTest(error=type(error).__name__):
                stderr = StringIO()
                command = Command(stdout=StringIO(), stderr=stderr)
                with patch('items.management.commands.import_dummyjson_items.requests.get', side_effect=error), \
                        patch('django.core.management.base.connections.close_all'):
                    with self.assertRaises(SystemExit) as stopped:
                        command.run_from_argv(['manage.py', 'import_dummyjson_items'] + ['--limit', '50', '--refresh'])
                self.assertEqual(stopped.exception.code, 1)
                self.assertIn('Gagal mengambil DummyJSON', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
