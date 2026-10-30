from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from account_profile.models import Review
from transactions.models import Transaction, TransactionItem
from .models import Item, ItemImage
from .test_photos import photo


class ItemDetailCardTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        User = get_user_model()
        self.seller = User.objects.create_user(username='detail_card_seller')
        self.buyer = User.objects.create_user(username='detail_card_buyer')
        self.item = Item.objects.create(owner=self.seller, title='Real uploaded item', description='Deskripsi asli pengguna',
                                        category='fashion', condition='good', listing_type='sale', price=54000, location='Depok')

    def upload(self, count):
        return [ItemImage.objects.create(item=self.item, image=photo(f'{i}.jpg'), order=i) for i in range(count)]

    def test_no_photos_is_safe_and_empty_location_does_not_invent_data(self):
        self.item.location = ''
        self.item.save()
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(response.context['gallery_photos'], [])
        self.assertEqual(response.context['gallery_extra_count'], 0)
        self.assertNotContains(response, 'data-gallery-src=')
        self.assertContains(response, 'No item photos available')
        self.assertNotContains(response, '<dt>Location</dt>')
        self.assertNotContains(response, 'Size:')
        self.assertContains(response, self.item.description)
        self.assertContains(response, 'No reviews yet')
        self.assertNotContains(response, 'item-review-breakdown')
        self.assertNotContains(response, 'More from this seller')

    def test_one_photo_has_one_main_photo_and_no_fake_thumbnails(self):
        image = self.upload(1)[0]
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(len(response.context['gallery_photos']), 1)
        self.assertEqual(response.context['gallery_thumbnails'], [])
        self.assertContains(response, image.image.url)
        self.assertNotContains(response, 'data-gallery-src=')

    def test_more_than_five_keeps_four_thumbnails_and_real_overflow(self):
        images = self.upload(8)
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(len(response.context['gallery_photos']), 8)
        self.assertEqual(len(response.context['gallery_thumbnails']), 4)
        self.assertEqual(response.context['gallery_extra_count'], 3)
        self.assertContains(response, 'class="item-gallery-more">+3')
        self.assertContains(response, 'id="item-photo-dialog"')
        self.assertContains(response, 'data-gallery-src=', count=4)
        self.assertEqual(response.context['gallery_photos'][0]['url'], images[0].image.url)
        self.assertEqual(response.context['gallery_photos'][-1]['url'], images[-1].image.url)

    def test_guest_buyer_owner_keep_existing_actions_and_photo_favorite(self):
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, f'{reverse("login")}?next={self.item.get_absolute_url()}')
        self.assertContains(response, 'data-item-favorite=')
        self.assertNotContains(response, 'id="item-add-to-cart-form"')
        self.client.force_login(self.buyer)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, 'id="item-add-to-cart-form"')
        self.assertContains(response, 'id="item-offer-open"')
        self.assertContains(response, reverse('transactions:pesan'))
        self.assertContains(response, reverse('transactions:checkout') + f'?item={self.item.pk}')
        self.assertContains(response, reverse('item_matching:request_create', args=[self.item.pk]))
        self.client.force_login(self.seller)
        response = self.client.get(self.item.get_absolute_url())
        self.assertNotContains(response, 'item-action-primary-row')
        self.assertNotContains(response, 'id="item-offer-open"')
        self.assertContains(response, reverse('items:item_update', args=[self.item.pk]))
        self.assertContains(response, reverse('items:item_delete', args=[self.item.pk]))

    def test_review_summary_breakdown_and_latest_three_are_real(self):
        self.client.force_login(self.buyer)
        for index, rating in enumerate([5, 5, 3, 3]):
            order = Transaction.objects.create(buyer=self.buyer, order_id=f'DETAIL-REVIEW-{index}', item_name=self.item.title,
                                                quantity=1, total_amount=54000, shipping_address='Depok', transaction_status='completed')
            TransactionItem.objects.create(transaction=order, item=self.item, seller=self.seller)
            Review.objects.create(transaction=order, reviewer=self.buyer, seller=self.seller, rating=rating, comment=f'Real review {index}')
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(response.context['seller_review_summary'], {'review_score': 4.0, 'review_count': 4})
        self.assertEqual(len(response.context['seller_reviews']), 3)
        breakdown = response.context['seller_review_breakdown']
        self.assertEqual([row['count'] for row in breakdown], [2, 0, 2, 0, 0])
        self.assertEqual(sum(row['percentage'] for row in breakdown), 100)
        self.assertNotContains(response, 'Real review 0')
        self.assertContains(response, 'Real review 3')
        self.assertContains(response, 'See all reviews')

    def test_only_other_available_items_from_same_seller_are_shown(self):
        other = Item.objects.create(owner=self.seller, title='Other real item', category='books', condition='good', listing_type='free')
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(list(response.context['seller_items']), [other])
        self.assertContains(response, 'More from this seller')
        self.assertContains(response, other.get_absolute_url())
