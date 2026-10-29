from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from items.models import Item
from .models import CartItem


class DetailCartAjaxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.seller = User.objects.create_user(username='ajax_cart_seller')
        self.buyer = User.objects.create_user(username='ajax_cart_buyer')
        self.other = User.objects.create_user(username='ajax_cart_other')
        self.item = Item.objects.create(owner=self.seller, title='Lampu AJAX', category='electronics',
                                        condition='good', listing_type='sale', price=54000, status='available')
        self.url = reverse('transactions:add_to_cart', args=[self.item.pk])
        self.client.force_login(self.buyer)

    def test_ajax_add_and_repeat_are_persistent_without_redirect_or_duplicates(self):
        session = self.client.session
        session['checkout_cart_entry_ids'] = [999]
        session.save()
        response = self.client.post(self.url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'created': True, 'message': 'Added to your cart', 'cart_count': 1})
        self.assertNotIn('Location', response)
        response = self.client.post(self.url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.json(), {'created': False, 'message': 'This item is already in your cart', 'cart_count': 1})
        self.assertEqual(CartItem.objects.filter(user=self.buyer, item=self.item).count(), 1)
        self.assertEqual(CartItem.objects.get(user=self.buyer, item=self.item).quantity, 1)
        self.assertEqual(self.client.session['checkout_cart_entry_ids'], [999])
        self.assertFalse(list(self.client.get(self.item.get_absolute_url()).context['messages']))

    def test_json_errors_do_not_redirect_or_modify_cart(self):
        self.assertEqual(self.client.get(self.url, HTTP_ACCEPT='application/json').status_code, 405)
        self.client.force_login(self.seller)
        response = self.client.post(self.url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn('own item', response.json()['error'])
        self.client.force_login(self.buyer)
        for status in ['sold', 'unavailable']:
            self.item.status = status
            self.item.save()
            response = self.client.post(self.url, HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('Location', response)
        self.assertFalse(CartItem.objects.filter(item=self.item).exists())

    def test_csrf_guest_next_and_existing_normal_post_contract(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.buyer)
        self.assertEqual(secure.post(self.url, HTTP_ACCEPT='application/json').status_code, 403)
        secure.get(self.item.get_absolute_url())
        self.assertEqual(secure.post(self.url, HTTP_ACCEPT='application/json',
                                    HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value).status_code, 200)
        self.assertRedirects(self.client.post(self.url), reverse('transactions:cart'))
        self.client.logout()
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, f'href="{reverse("login")}?next={self.item.get_absolute_url()}" aria-label="Add to cart"')
        response = self.client.post(self.url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login') + '?next='))

    def test_one_left_nav_cart_correct_target_and_form_even_if_already_added(self):
        CartItem.objects.create(user=self.buyer, item=self.item)
        response = self.client.get(self.item.get_absolute_url())
        html = response.content.decode()
        header = html.split('<header class="site-header">', 1)[1].split('<div class="site-toast-region"', 1)[0]
        self.assertEqual(header.count('nav-cart-link'), 1)
        self.assertIn(reverse('transactions:cart'), header)
        self.assertLess(header.index('nav-cart-link'), header.index('nav-matching-trigger'))
        self.assertLess(header.index('nav-cart-link'), header.index('nav-profile-menu'))
        self.assertContains(response, 'aria-label="Cart, 1 items"')
        self.assertContains(response, 'id="item-add-to-cart-form"')
        self.assertContains(response, 'form="item-add-to-cart-form"')
        self.assertContains(response, 'js/items/cart.js')

    def test_count_and_cart_mutation_are_scoped_to_current_user(self):
        CartItem.objects.create(user=self.other, item=self.item)
        self.assertEqual(self.client.post(self.url, HTTP_ACCEPT='application/json').json()['cart_count'], 1)
        self.assertEqual(CartItem.objects.filter(user=self.other, item=self.item).count(), 1)
