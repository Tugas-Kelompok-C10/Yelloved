from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from .models import WantedPost


class WantedBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        # Browser tests should test our UI, not depend on the external API.
        samples = patch('wanted_board.views.get_sample_wanted_posts', return_value=())
        samples.start()
        self.addCleanup(samples.stop)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1440,1000')
        self.browser = webdriver.Chrome(options=options)
        self.addCleanup(self.browser.quit)
        self.wait = WebDriverWait(self.browser, 10)

    def open_board(self, authenticated=False):
        url = self.live_server_url + reverse('wanted_board:show_wanted')
        if authenticated:
            self.owner = get_user_model().objects.create_user(username='browser-owner')
            # Authenticate the test browser using a real Django session cookie.
            self.client.force_login(self.owner)
            self.browser.get(url)
            self.browser.add_cookie({
                'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                'path': '/',
            })
        self.browser.get(url)
        self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.wanted-page h1')))

    def click(self, selector):
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector))).click()

    def fill(self, modal, name, value):
        field = self.browser.find_element(By.CSS_SELECTOR, f'{modal} [name="{name}"]')
        field.clear()
        field.send_keys(value)

    def test_board_can_be_opened(self):
        self.open_board()
        self.assertEqual(self.browser.find_element(By.CSS_SELECTOR, '.wanted-page h1').text, 'Wanted Board')

    def test_create_edit_delete_without_reloading_document(self):
        self.open_board(authenticated=True)
        document = self.browser.find_element(By.TAG_NAME, 'html')
        self.click('[data-open-wanted-modal]')
        for name, value in {'title': 'Browser study lamp', 'description': 'A lamp for studying.',
                            'budget': '100000', 'location': 'Kukusan'}.items():
            self.fill('#create-wanted-modal', name, value)
        Select(self.browser.find_element(By.CSS_SELECTOR, '#create-wanted-modal [name=category]')).select_by_value('electronics')
        self.click('#create-wanted-modal [type=submit].wanted-action-offer')
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '.wanted-grid'), 'Browser study lamp'))
        self.assertEqual(self.browser.find_element(By.TAG_NAME, 'html'), document)
        post = WantedPost.objects.get(title='Browser study lamp')
        self.assertEqual(post.requester_id, self.owner.pk)

        self.click('.wanted-card-link')
        self.click('[data-open-edit-wanted-modal]')
        document = self.browser.find_element(By.TAG_NAME, 'html')
        self.fill('#edit-wanted-modal', 'title', 'Updated browser lamp')
        self.click('#edit-wanted-modal [type=submit]')
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '.wanted-detail-card h1'), 'Updated browser lamp'))
        self.wait.until(EC.invisibility_of_element_located((By.ID, 'edit-wanted-modal')))
        self.assertEqual(self.browser.find_element(By.TAG_NAME, 'html'), document)
        post.refresh_from_db()
        self.assertEqual(post.title, 'Updated browser lamp')

        self.click('[data-open-delete-wanted-modal]')
        self.click('#delete-wanted-modal [type=submit]')
        # Wait for server confirmation as well as the optimistic visual update.
        self.wait.until(lambda _: not WantedPost.objects.filter(pk=post.pk).exists())
        self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.wanted-page h1')))
        self.assertEqual(self.browser.find_element(By.TAG_NAME, 'html'), document)
        self.assertEqual(self.browser.find_elements(By.CSS_SELECTOR, '.wanted-card'), [])

    def test_required_fields_and_zero_budget_cannot_create_post(self):
        self.open_board(authenticated=True)
        self.click('[data-open-wanted-modal]')
        self.click('#create-wanted-modal [type=submit].wanted-action-offer')
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#create-wanted-modal [name=title]:invalid')))
        self.assertFalse(WantedPost.objects.exists())

        for name, value in {'title': 'Invalid budget lamp', 'description': 'A study lamp.',
                            'budget': '0', 'location': 'Kukusan'}.items():
            self.fill('#create-wanted-modal', name, value)
        Select(self.browser.find_element(By.CSS_SELECTOR, '#create-wanted-modal [name=category]')).select_by_value('electronics')
        self.click('#create-wanted-modal [type=submit].wanted-action-offer')
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#create-wanted-modal [name=budget]:invalid')))
        self.assertTrue(self.browser.find_element(By.ID, 'create-wanted-modal').is_displayed())
        self.assertFalse(WantedPost.objects.exists())

    def test_htmx_search_category_sort_and_pagination_work_together(self):
        owner = get_user_model().objects.create_user(username='browser-books-owner')
        WantedPost.objects.bulk_create([
            WantedPost(requester=owner, title=f'Browser book {number}', category='books', budget=(number + 1) * 1000)
            for number in range(14)
        ])
        WantedPost.objects.create(requester=owner, title='Browser lamp', category='electronics', budget=1000)
        self.open_board()
        document = self.browser.find_element(By.TAG_NAME, 'html')
        query = self.browser.find_element(By.ID, 'wanted-query')
        query.send_keys('Browser book')
        self.wait.until(lambda browser: 'q=Browser+book' in browser.current_url)
        self.assertNotIn('Browser lamp', self.browser.find_element(By.CSS_SELECTOR, '.wanted-grid').text)
        self.click('[data-category-chip="books"]')
        self.wait.until(lambda browser: 'category=books' in browser.current_url)
        self.click('[data-wanted-sort]')
        self.wait.until(lambda browser: 'sort=budget_asc' in browser.current_url)
        self.assertEqual(self.browser.find_element(By.CSS_SELECTOR, '.wanted-card h3').text, 'Browser book 0')
        self.click('[data-wanted-page="2"]')
        self.wait.until(lambda browser: 'page=2' in browser.current_url)
        self.assertEqual(len(self.browser.find_elements(By.CSS_SELECTOR, '.wanted-card')), 2)
        self.assertEqual(self.browser.find_element(By.CSS_SELECTOR, '.wanted-card h3').text, 'Browser book 12')
        self.assertEqual(self.browser.find_element(By.ID, 'wanted-query'), query)
        self.assertEqual(self.browser.find_element(By.TAG_NAME, 'html'), document)
