from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Item


class FavoriteTests(TestCase):
    def setUp(self):
        # These tests supply their own catalogue fixtures, independent of startup seeds.
        Item.objects.filter(external_id__range=(10000001, 10000020)).delete()
        users = get_user_model()
        self.seller = users.objects.create_user(username='favorite_seller')
        self.buyer = users.objects.create_user(username='favorite_buyer')
        self.other = users.objects.create_user(username='favorite_other')
        self.item = Item.objects.create(
            owner=self.seller, title='Lampu belajar', description='Lampu kos',
            category='electronics', condition='good', price=54000,
            listing_type='sale', location='Kukusan, Depok',
            image_url='/static/img/items/catalog/item-071.webp',
        )
        self.url = reverse('items:toggle_favorite', args=[self.item.pk])

    def test_toggle_persists_and_is_private_to_each_user(self):
        self.client.force_login(self.buyer)
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'item_id': self.item.pk, 'is_favorited': True})
        self.assertTrue(self.buyer.favorite_items.filter(pk=self.item.pk).exists())
        # The saved state is read from the database on both full pages and AJAX results.
        for url in (reverse('items:explore_items'), self.item.get_absolute_url()):
            self.assertContains(self.client.get(url), 'aria-pressed="true"')
        data = self.client.get(reverse('items:items_json')).json()
        self.assertTrue(data['items'][0]['is_favorited'])
        self.assertIn('aria-pressed="true"', data['html'])
        self.client.force_login(self.other)
        self.assertFalse(self.client.get(reverse('items:items_json')).json()['items'][0]['is_favorited'])
        self.client.post(self.url)
        self.client.force_login(self.buyer)
        self.assertFalse(self.client.post(self.url).json()['is_favorited'])
        self.assertFalse(self.buyer.favorite_items.exists())
        self.assertTrue(self.other.favorite_items.filter(pk=self.item.pk).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.owner, self.seller)
        self.assertEqual(self.item.price, 54000)

    def test_authentication_post_only_csrf_and_missing_item(self):
        self.assertRedirects(self.client.post(self.url), '/accounts/login/?next=' + self.url,
                             fetch_redirect_response=False)
        self.assertFalse(self.item.liked_by.exists())
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(reverse('items:toggle_favorite', args=[999999])).status_code, 404)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.buyer)
        self.assertEqual(secure.post(self.url).status_code, 403)
        secure.get(self.item.get_absolute_url())
        response = secure.post(self.url, HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_favorited'])

    def test_guest_login_next_and_owner_actions_remain(self):
        response = self.client.get(reverse('items:explore_items') + '?category=electronics')
        self.assertContains(response, 'next=/explore/%3Fcategory%3Delectronics')
        self.assertContains(response, 'data-item-favorite="%s"' % self.item.pk)
        self.assertContains(response, 'aria-pressed="false"')
        self.client.force_login(self.seller)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, reverse('items:item_update', args=[self.item.pk]))
        self.assertNotContains(response, 'id="item-offer-open"')
        self.assertNotContains(response, 'item-action-primary-row')

    def test_detail_keeps_existing_action_routes_and_modal(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, 'item-action-primary-row')
        html = response.content.decode()
        primary_row = html.split('class="item-action-primary-row"', 1)[1].split('</div>', 1)[0]
        self.assertIn('item-cart-button', primary_row)
        self.assertNotIn('data-item-favorite', primary_row)
        photo = html.split('class="explore-image explore-detail-image"', 1)[1].split('</figure>', 1)[0]
        self.assertIn('data-item-favorite', photo)
        self.assertContains(response, 'id="item-offer-open"')
        self.assertContains(response, 'data-item-favorite="%s"' % self.item.pk)
        self.assertContains(response, reverse('transactions:checkout'))
        self.assertContains(response, reverse('transactions:pesan'))
        self.assertContains(response, 'action="%s"' % reverse('item_matching:request_create', args=[self.item.pk]))
        self.assertNotContains(response, '>Actions</h2>')


    def test_more_from_seller_is_real_available_and_excludes_current(self):
        def listing(owner, title, status='available'):
            return Item.objects.create(owner=owner, title=title, category='books',
                                       condition='good', listing_type='free', status=status)
        sibling = listing(self.seller, 'Buku dari seller yang sama')
        listing(self.other, 'Barang seller lain')
        listing(self.seller, 'Barang sudah terjual', 'sold')
        self.client.force_login(self.buyer)
        sibling.liked_by.add(self.buyer)
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(list(response.context['seller_items']), [sibling])
        self.assertContains(response, sibling.get_absolute_url())
        self.assertContains(response, 'More from this seller')
        self.assertContains(response, 'aria-pressed="true"')
        sibling.delete()
        self.assertContains(self.client.get(self.item.get_absolute_url()),
                            'No other available listings from this seller yet.')
        self.item.owner = None
        self.item.save()
        listing(None, 'Unassigned listing')
        self.assertFalse(self.client.get(self.item.get_absolute_url()).context['seller_items'].exists())
