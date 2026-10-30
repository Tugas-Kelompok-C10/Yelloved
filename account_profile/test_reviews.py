from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from items.models import Item
from transactions.models import Transaction, TransactionItem
from transactions.views import snapshot_review_sellers
from .models import Review


class SellerReviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username='review_buyer')
        self.seller = User.objects.create_user(username='review_seller')
        self.other = User.objects.create_user(username='review_other')
        self.item = Item.objects.create(owner=self.seller, title='Review item', category='books',
                                       condition='good', listing_type='sale', price=50000)
        self.order = Transaction.objects.create(order_id='REVIEW-ONE', buyer=self.buyer, item_name=self.item.title,
                                                quantity=1, total_amount=50000, shipping_address='Depok',
                                                transaction_status='completed')
        snapshot_review_sellers(self.order, [{'item': self.item, 'quantity': 1}])
        self.url = reverse('account_profile:reviews')
        self.profile = reverse('account_profile:user_profile', args=[self.seller.username])
        self.data = {'transaction_id': self.order.pk, 'seller': self.seller.pk, 'rating': '5', 'comment': 'Sesuai deskripsi. Terima kasih!'}
        self.client.force_login(self.buyer)

    def test_completed_buyer_can_submit_once_and_summary_is_real(self):
        self.assertContains(self.client.get(self.profile, {'tab': 'reviews'}), 'No reviews yet')
        self.assertContains(self.client.get(reverse('transactions:transaction_history')), 'Leave a review')
        response = self.client.post(self.url, self.data)
        self.assertRedirects(response, self.url + '?tab=mine')
        self.assertEqual(Review.objects.count(), 1)
        self.assertContains(self.client.get(reverse('transactions:transaction_history')), 'Review submitted')
        response = self.client.post(self.url, {**self.data, 'rating': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.get().rating, 5)
        profile = self.client.get(self.profile, {'tab': 'reviews'})
        self.assertEqual(profile.context['profile_stats'], {'review_score': 5.0, 'review_count': 1})
        self.assertContains(profile, '5.0 ★ (1 review)')
        self.assertContains(profile, self.data['comment'])
        self.assertContains(profile, self.buyer.username)
        self.assertNotContains(profile, 'public-profile-impact')
        self.assertNotContains(profile, 'followers')
        detail = self.client.get(self.item.get_absolute_url())
        self.assertContains(detail, 'Seller reviews')
        self.assertContains(detail, self.data['comment'])
        self.assertContains(detail, self.profile + '?tab=reviews')

    def test_pending_processing_failed_and_cancelled_orders_cannot_be_reviewed(self):
        for status in ['pending', 'processing', 'cancelled']:
            self.order.transaction_status = status
            self.order.save()
            self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
            self.assertNotContains(self.client.get(reverse('transactions:transaction_history')), 'Leave a review')
            with self.assertRaises(ValidationError):
                Review.objects.create(transaction=self.order, reviewer=self.buyer, seller=self.seller, rating=5)
        self.assertFalse(Review.objects.exists())

    def test_other_user_and_self_review_cannot_spoof_buyer_or_seller(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(self.url, {**self.data, 'seller': self.other.pk}).status_code, 200)
        self.assertFalse(Review.objects.exists())
        self.order.buyer = self.seller
        self.order.save()
        self.client.force_login(self.seller)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_rating_and_csrf_are_validated_and_comments_are_escaped(self):
        for rating in ['0', '6', '-1', '3.5', '', 'bad']:
            response = self.client.post(self.url, {**self.data, 'rating': rating})
            self.assertEqual(response.status_code, 200)
            self.assertIn('rating', response.context['review_form'].errors)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.buyer)
        self.assertEqual(secure.post(self.url, self.data).status_code, 403)
        secure.get(self.url, {'order': self.order.pk})
        response = secure.post(self.url, {**self.data, 'comment': '<script>alert(1)</script>'},
                               HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(self.profile, {'tab': 'reviews'}), '&lt;script&gt;')
        self.assertNotContains(self.client.get(self.profile, {'tab': 'reviews'}), '<script>alert(1)</script>')

    def test_latest_two_and_average_count(self):
        for number, rating in enumerate([5, 3, 4]):
            order = Transaction.objects.create(order_id=f'REVIEW-{number}', buyer=self.buyer, item_name='Real item',
                                                total_amount=50000, shipping_address='Depok', transaction_status='completed')
            snapshot_review_sellers(order, [{'item': self.item}])
            Review.objects.create(transaction=order, reviewer=self.buyer, seller=self.seller, rating=rating, comment=f'Review comment {number}')
        profile = self.client.get(self.profile, {'tab': 'reviews'})
        self.assertEqual(profile.context['profile_stats'], {'review_score': 4.0, 'review_count': 3})
        self.assertEqual(profile.context['seller_reviews'].count(), 3)
        detail = self.client.get(self.item.get_absolute_url())
        self.assertEqual(len(detail.context['seller_reviews']), 3)
        self.assertContains(detail, 'Review comment 2')
        self.assertContains(detail, 'Review comment 0')

    def test_unknown_historical_seller_is_never_guessed_and_guest_cannot_post(self):
        TransactionItem.objects.all().delete()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertNotContains(self.client.get(reverse('transactions:transaction_history')), 'Leave a review')
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.assertEqual(self.client.get(self.profile, {'tab': 'reviews'}).status_code, 200)

    def test_checkout_records_real_seller_and_review_stays_locked_until_completed(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        with patch('builtins.print'):
            response = self.client.post(reverse('transactions:checkout') + f'?item={self.item.pk}', {
                'action': 'select_payment', 'payment_method': 'cod',
                'cod_meeting_location': 'Area UI, Depok',
                'cod_meeting_time': (timezone.now() + timedelta(days=1)).isoformat(),
            })
        self.assertEqual(response.status_code, 302)
        created = Transaction.objects.exclude(pk=self.order.pk).get(buyer=self.buyer)
        self.assertEqual(created.transaction_status, 'pending')
        self.assertEqual(created.review_items.get().seller, self.seller)
        self.assertEqual(created.review_items.get().item, self.item)
        data = {**self.data, 'transaction_id': created.pk}
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        created.transaction_status = 'completed'
        created.save()
        # Ownership changes cannot redirect a completed purchase's review to a different seller.
        self.item.owner = self.other
        self.item.save()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(Review.objects.get(transaction=created).seller, self.seller)
