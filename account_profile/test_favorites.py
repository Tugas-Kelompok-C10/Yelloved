from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from items.models import Item


class ProfileFavoritesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='profile_favorites_user')
        self.other = get_user_model().objects.create_user(username='profile_other_user')
        self.seller = get_user_model().objects.create_user(username='profile_item_seller')
        self.url = reverse('account_profile:user_profile', args=[self.user.username])
        self.other_url = reverse('account_profile:user_profile', args=[self.other.username])
        self.items = []
        for index, listing_type in enumerate(('sale', 'free', 'swap')):
            item = Item.objects.create(
                owner=self.seller, title=f'Real favorite {listing_type}',
                description='User content stays unchanged', category='books', condition='good',
                price=54000 if listing_type == 'sale' else None, listing_type=listing_type,
                location='Kukusan, Depok', image_url=f'/static/img/items/catalog/item-{index + 1:03d}.webp',
            )
            item.liked_by.add(self.user)
            self.items.append(item)
        self.private_item = Item.objects.create(owner=self.seller, title='Other user private favorite',
                                                category='books', condition='good', listing_type='free')
        self.private_item.liked_by.add(self.other)

    def test_only_own_favorites_are_accessible(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, {'tab': 'favorites'})
        self.assertEqual(response.context['active_tab'], 'favorites')
        self.assertEqual(response.context['favorites_total'], 3)
        self.assertContains(response, 'Your favorites (')
        for item in self.items:
            self.assertContains(response, item.title)
            self.assertContains(response, item.display_image_url)
        self.assertNotContains(response, self.private_item.title)
        for params in ({'tab': 'favorites'}, {'tab': 'favorites', 'fragment': 'favorites'}):
            self.assertEqual(self.client.get(self.other_url, params).status_code, 403)
        self.assertContains(response, 'href="?tab=favorites" class="is-active" aria-current="page"')
        self.assertContains(response, 'Edit profile')
        self.assertNotContains(response, 'followers')

    def test_listing_type_filters_are_real_in_full_and_partial_responses(self):
        self.client.force_login(self.user)
        for item in self.items:
            for fragment in ('', 'favorites'):
                response = self.client.get(self.url, {'tab': 'favorites', 'listing_type': item.listing_type, 'fragment': fragment})
                self.assertEqual(list(response.context['favorites']), [item])
                self.assertContains(response, item.title)
                for excluded in self.items:
                    if excluded != item:
                        self.assertNotContains(response, excluded.title)
                if fragment:
                    self.assertNotContains(response, '<html')
        response = self.client.get(self.url, {'tab': 'favorites', 'listing_type': 'invalid'})
        self.assertEqual(response.context['favorites'].count(), 3)

    def test_unfavorite_uses_items_endpoint_with_csrf_and_updates_partial(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        item = self.items[0]
        response = client.get(self.url, {'tab': 'favorites'})
        toggle_url = reverse('items:toggle_favorite', args=[item.pk])
        self.assertContains(response, f'data-url="{toggle_url}"')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertEqual(client.post(toggle_url).status_code, 403)
        response = client.post(toggle_url, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.json(), {'item_id': item.pk, 'is_favorited': False})
        self.assertFalse(item.liked_by.filter(pk=self.user.pk).exists())
        response = client.get(self.url, {'tab': 'favorites', 'fragment': 'favorites'})
        self.assertNotContains(response, item.title)
        self.assertEqual(response.context['favorites_total'], 2)
        self.assertTrue(self.private_item.liked_by.filter(pk=self.other.pk).exists())

    def test_guest_favorites_requires_login_but_public_tabs_remain_public(self):
        for fragment in ('', 'favorites'):
            response = self.client.get(self.url, {'tab': 'favorites', 'fragment': fragment})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse('login') + '?next='))
            self.assertNotContains(response, self.items[0].title, status_code=302)
        for tab in ('posted', 'wanted', 'reviews'):
            self.assertEqual(self.client.get(self.url, {'tab': tab}).status_code, 200)

    def test_empty_state_and_previous_tabs(self):
        self.client.force_login(self.user)
        for item in self.items:
            item.liked_by.remove(self.user)
        response = self.client.get(self.url, {'tab': 'favorites'})
        self.assertContains(response, 'You have no favorites yet.')
        self.assertContains(response, 'Browse catalogue')
        self.assertContains(response, reverse('items:explore_items'))
        posted = Item.objects.create(owner=self.user, title='My posted item', category='fashion',
                                     condition='good', listing_type='free')
        self.assertContains(self.client.get(self.url, {'tab': 'posted'}), posted.title)
        self.assertContains(self.client.get(self.url, {'tab': 'wanted'}), 'No wanted posts yet.')
        self.assertContains(self.client.get(self.url, {'tab': 'reviews'}), 'No reviews yet.')
