from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from .views import _page_numbers


class WantedPaginationTests(SimpleTestCase):
    def test_page_numbers_are_bounded_and_keep_current_and_endpoints(self):
        for total in range(1, 40):
            for current in range(1, total + 1):
                links = _page_numbers(current, total)
                numbers = [number for number in links if isinstance(number, int)]
                self.assertLessEqual(len(numbers), 6)
                self.assertEqual(numbers, sorted(set(numbers)))
                self.assertEqual(numbers[0], 1)
                self.assertEqual(numbers[-1], total)
                self.assertIn(current, numbers)
                for index, number in enumerate(links):
                    if number == Paginator.ELLIPSIS:
                        self.assertGreater(links[index + 1] - links[index - 1], 1)

    def markup(self, current, total):
        paginator = Paginator(range(total * 12), 12)
        page = paginator.page(current)
        return render_to_string("wanted_board/_pagination.html", {
            "page_obj": page,
            "pagination_links": [
                {"number": number, "url": f"?page={number}" if isinstance(number, int) else None}
                for number in _page_numbers(current, total)
            ],
            "previous_page_url": f"?page={current - 1}" if page.has_previous() else None,
            "next_page_url": f"?page={current + 1}" if page.has_next() else None,
        })

    def test_both_arrows_remain_visible_at_start_end_and_single_page(self):
        for current, total in ((1, 10), (10, 10), (1, 1)):
            html = self.markup(current, total)
            self.assertEqual(html.count('aria-label="Previous page"'), 1)
            self.assertEqual(html.count('aria-label="Next page"'), 1)
            self.assertEqual(html.count('aria-disabled="true"'), 2 if total == 1 else 1)
        self.assertIn('disabled aria-disabled="true" aria-label="Previous page"', self.markup(1, 10))
        self.assertIn('disabled aria-disabled="true" aria-label="Next page"', self.markup(10, 10))
