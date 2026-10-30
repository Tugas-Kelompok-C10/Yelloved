from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from items.models import Item
from wanted_board.models import WantedPost

from . import services
from .matching import evaluate, suggest_items_for_wanted, suggest_wanted_for_item
from .models import ItemOffer, ItemRequest
from .services import MatchingError

User = get_user_model()


def make_item(owner, **kw):
    data = dict(title='Lampu belajar', description='Lampu meja LED untuk belajar', category='home',
                condition='good', listing_type='sale', price=Decimal('50000'), location='Kukusan',
                image_url='https://example.com/a.jpg')
    data.update(kw)
    return Item.objects.create(owner=owner, **data)


def make_post(requester, **kw):
    data = dict(title='Lampu belajar', description='Butuh lampu meja kecil', category='home',
                budget=Decimal('100000'), location='Kukusan')
    data.update(kw)
    return WantedPost.objects.create(requester=requester, **data)


class Base(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.other = User.objects.create_user('other', password='pw')


class ItemRequestRulesTests(Base):
    def test_cannot_request_own_item(self):
        item = make_item(self.owner)
        self.client.force_login(self.owner)
        r = self.client.post(reverse('item_matching:request_create', args=[item.pk]), {'message': 'hi'})
        self.assertRedirects(r, item.get_absolute_url())
        self.assertFalse(ItemRequest.objects.exists())

    def test_request_created_and_duplicate_pending_blocked(self):
        item = make_item(self.owner)
        self.client.force_login(self.buyer)
        url = reverse('item_matching:request_create', args=[item.pk])
        self.client.post(url, {'offer_price': '45000', 'message': 'mau'})
        self.assertEqual(ItemRequest.objects.count(), 1)
        r = self.client.post(url, {'offer_price': '40000', 'message': 'lagi'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ItemRequest.objects.count(), 1)

    def test_unavailable_and_catalog_items_cannot_be_requested(self):
        sold = make_item(self.owner, status='sold')
        catalog = make_item(None, source='dummyjson', external_id=1)
        self.client.force_login(self.buyer)
        for item in (sold, catalog):
            self.client.post(reverse('item_matching:request_create', args=[item.pk]), {})
        self.assertFalse(ItemRequest.objects.exists())

    def test_login_required(self):
        item = make_item(self.owner)
        r = self.client.get(reverse('item_matching:request_create', args=[item.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_swap_requires_own_available_item(self):
        swap = make_item(self.owner, listing_type='swap', price=None)
        mine = make_item(self.buyer, title='Tas')
        theirs = make_item(self.other, title='Sepatu')
        self.client.force_login(self.buyer)
        url = reverse('item_matching:request_create', args=[swap.pk])
        self.client.post(url, {'message': 'x'})
        self.client.post(url, {'message': 'x', 'offered_item': theirs.pk})
        self.assertFalse(ItemRequest.objects.exists())
        self.client.post(url, {'message': 'x', 'offered_item': mine.pk})
        self.assertEqual(ItemRequest.objects.get().offered_item, mine)

    def test_non_swap_hides_offered_item_field(self):
        item = make_item(self.owner)
        self.client.force_login(self.buyer)
        r = self.client.get(reverse('item_matching:request_create', args=[item.pk]))
        self.assertNotIn('offered_item', r.context['form'].fields)


class OfferPriceTests(Base):
    """The offer amount (offer_price) on item requests."""

    def url(self, item):
        return reverse('item_matching:request_create', args=[item.pk])

    def test_sale_request_saves_offer_price_and_optional_message(self):
        item = make_item(self.owner)
        self.client.force_login(self.buyer)
        r = self.client.post(self.url(item), {'offer_price': '45000'})     # tanpa pesan
        self.assertRedirects(r, reverse('item_matching:dashboard') + '?tab=sent')
        req = ItemRequest.objects.get()
        self.assertEqual(req.offer_price, Decimal('45000'))
        self.assertEqual(req.message, '')
        self.assertEqual(req.offer_price_display, 'Rp45.000')

    def test_sale_request_requires_a_positive_offer_price(self):
        item = make_item(self.owner)
        self.client.force_login(self.buyer)
        for bad in ({}, {'offer_price': ''}, {'offer_price': '0'}, {'offer_price': '-5000'},
                    {'offer_price': 'abc'}):
            r = self.client.post(self.url(item), bad)
            self.assertEqual(r.status_code, 200)
            self.assertIn('offer_price', r.context['form'].errors)
        self.assertFalse(ItemRequest.objects.exists())

    def test_free_and_swap_items_have_no_offer_price_field(self):
        free = make_item(self.owner, listing_type='free', price=None)
        swap = make_item(self.owner, title='Kipas', listing_type='swap', price=None)
        mine = make_item(self.buyer, title='Tas')
        self.client.force_login(self.buyer)
        r = self.client.get(self.url(free))
        self.assertNotIn('offer_price', r.context['form'].fields)
        # nominal yang ikut terkirim tetap diabaikan
        self.client.post(self.url(free), {'offer_price': '1000'})
        self.client.post(self.url(swap), {'offer_price': '1000', 'offered_item': mine.pk})
        self.assertEqual(ItemRequest.objects.count(), 2)
        self.assertFalse(ItemRequest.objects.exclude(offer_price=None).exists())

    def test_model_rejects_offer_price_on_non_sale_item(self):
        free = make_item(self.owner, listing_type='free', price=None)
        req = ItemRequest(item=free, requester=self.buyer, offer_price=Decimal('1000'))
        with self.assertRaises(ValidationError):
            req.full_clean()

    def test_dashboard_shows_offer_price_on_request_tabs(self):
        item = make_item(self.owner)
        ItemRequest.objects.create(item=item, requester=self.buyer, offer_price=Decimal('45000'))
        dash = reverse('item_matching:dashboard')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(dash, {'tab': 'incoming'}), 'Rp45.000')
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(dash, {'tab': 'sent'}), 'Rp45.000')


class RequestTransitionTests(Base):
    def setUp(self):
        super().setUp()
        self.item = make_item(self.owner)
        self.req = ItemRequest.objects.create(item=self.item, requester=self.buyer)
        self.req2 = ItemRequest.objects.create(item=self.item, requester=self.other)

    def test_accept_reserves_item_and_rejects_rivals(self):
        services.accept_request(self.req.pk, self.owner)
        self.req.refresh_from_db(); self.req2.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(self.req.status, 'accepted')
        self.assertEqual(self.req2.status, 'rejected')
        self.assertEqual(self.item.status, Item.Status.UNAVAILABLE)

    def test_only_owner_can_accept_or_reject(self):
        for fn in (services.accept_request, services.reject_request):
            with self.assertRaises(MatchingError):
                fn(self.req.pk, self.buyer)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'pending')

    def test_only_requester_can_cancel_and_only_when_pending(self):
        with self.assertRaises(MatchingError):
            services.cancel_request(self.req.pk, self.owner)
        services.cancel_request(self.req.pk, self.buyer)
        with self.assertRaises(MatchingError):
            services.cancel_request(self.req.pk, self.buyer)

    def test_cannot_accept_twice(self):
        services.accept_request(self.req.pk, self.owner)
        with self.assertRaises(MatchingError):
            services.accept_request(self.req.pk, self.owner)

    def test_swap_accept_reserves_both_and_cancels_dependants(self):
        swap = make_item(self.owner, title='Buku', listing_type='swap', price=None)
        mine = make_item(self.buyer, title='Tas')
        req = ItemRequest.objects.create(item=swap, requester=self.buyer, offered_item=mine)
        other_swap = make_item(self.other, title='Meja', listing_type='swap', price=None)
        dependant = ItemRequest.objects.create(item=other_swap, requester=self.buyer, offered_item=mine)
        services.accept_request(req.pk, self.owner)
        mine.refresh_from_db(); dependant.refresh_from_db()
        self.assertEqual(mine.status, Item.Status.UNAVAILABLE)
        self.assertEqual(dependant.status, 'cancelled')

    def test_action_views_are_post_only_and_enforce_owner(self):
        url = reverse('item_matching:request_accept', args=[self.req.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.buyer)
        self.client.post(url)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'pending')
        self.client.force_login(self.owner)
        self.client.post(url)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'accepted')


class ItemOfferTests(Base):
    def setUp(self):
        super().setUp()
        self.post = make_post(self.buyer)
        self.item = make_item(self.owner)

    def test_offer_flow_and_acceptance(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]),
                             {'item': self.item.pk, 'message': 'ada nih'})
        self.assertEqual(r.status_code, 302)
        offer = ItemOffer.objects.get()
        rival = ItemOffer.objects.create(wanted_post=self.post, item=make_item(self.other), offerer=self.other)
        services.accept_offer(offer.pk, self.buyer)
        offer.refresh_from_db(); rival.refresh_from_db(); self.post.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')
        self.assertEqual(rival.status, 'rejected')
        self.assertEqual(self.post.status, WantedPost.Status.MATCHED)
        self.assertEqual(self.item.status, Item.Status.UNAVAILABLE)

    def test_cannot_offer_on_own_post_or_someone_elses_item(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]), {'item': self.item.pk})
        self.client.force_login(self.other)
        self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]), {'item': self.item.pk})
        self.assertFalse(ItemOffer.objects.exists())

    def test_closed_post_rejects_offers(self):
        self.post.status = WantedPost.Status.CLOSED
        self.post.save()
        self.client.force_login(self.owner)
        self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]), {'item': self.item.pk})
        self.assertFalse(ItemOffer.objects.exists())

    def test_only_post_owner_decides_and_only_offerer_withdraws(self):
        offer = ItemOffer.objects.create(wanted_post=self.post, item=self.item, offerer=self.owner)
        with self.assertRaises(MatchingError):
            services.accept_offer(offer.pk, self.other)
        with self.assertRaises(MatchingError):
            services.reject_offer(offer.pk, self.owner)
        with self.assertRaises(MatchingError):
            services.withdraw_offer(offer.pk, self.buyer)
        services.withdraw_offer(offer.pk, self.owner)
        self.assertEqual(ItemOffer.objects.get().status, 'withdrawn')

    def test_same_item_cannot_be_offered_twice(self):
        ItemOffer.objects.create(wanted_post=self.post, item=self.item, offerer=self.owner)
        self.client.force_login(self.owner)
        self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]), {'item': self.item.pk})
        self.assertEqual(ItemOffer.objects.count(), 1)


class WantedOfferModalTests(Base):
    """Wanted photo offers are independent of existing catalogue listings."""

    def setUp(self):
        super().setUp()
        self.post = make_post(self.buyer)                    # pembuat wanted post
        self.detail = reverse('wanted_board:wanted_detail', args=[self.post.pk])

    def test_detail_uses_photo_offer_form_instead_of_listing_picker(self):
        mine = make_item(self.owner, title='Lampu saya')
        make_item(self.owner, title='Sudah terjual', status='sold')
        make_item(self.other, title='Punya orang lain')
        self.client.force_login(self.owner)
        r = self.client.get(self.detail)
        self.assertContains(r, 'name="image"')
        self.assertContains(r, 'name="price"')
        self.assertContains(r, 'name="description"')
        self.assertNotContains(r, 'Sudah terjual')
        self.assertNotContains(r, 'Punya orang lain')
        self.assertNotContains(r, 'name="item"')

    def test_offer_form_available_without_a_catalogue_listing(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.detail)
        self.assertContains(r, 'Send offer')
        self.assertContains(r, 'name="image"')
        self.assertNotContains(r, 'name="item"')

    def test_anonymous_visitor_is_asked_to_log_in(self):
        r = self.client.get(self.detail)
        self.assertContains(r, reverse('login'))
        self.assertNotContains(r, 'name="item"')

    def test_submitting_modal_form_creates_offer(self):
        mine = make_item(self.owner, title='Lampu saya')
        self.client.force_login(self.owner)
        r = self.client.post(reverse('item_matching:offer_create', args=[self.post.pk]), {'item': mine.pk})
        self.assertRedirects(r, reverse('item_matching:dashboard') + '?tab=offers_sent')
        offer = ItemOffer.objects.get()
        self.assertEqual((offer.item, offer.offerer, offer.message), (mine, self.owner, ''))


class MatchingScoreTests(Base):
    def test_matching_item_scores_and_explains(self):
        m = evaluate(make_item(self.owner), make_post(self.buyer))
        self.assertIsNotNone(m)
        self.assertIn('Same category', m.reasons)

    def test_hard_filters(self):
        post = make_post(self.buyer)
        self.assertIsNone(evaluate(make_item(self.owner, price=Decimal('500000')), post))   # over budget
        self.assertIsNone(evaluate(make_item(self.owner, listing_type='swap', price=None), post))
        self.assertIsNone(evaluate(make_item(self.owner, status='sold'), post))
        self.assertIsNone(evaluate(make_item(self.buyer), post))                             # own item
        self.assertIsNotNone(evaluate(make_item(self.owner, listing_type='free', price=None), post))

    def test_unrelated_item_does_not_match(self):
        item = make_item(self.owner, title='Kemeja flanel', description='Kemeja kotak', category='fashion')
        self.assertIsNone(evaluate(item, make_post(self.buyer)))

    def test_suggestions_sorted_best_first_both_directions(self):
        best = make_item(self.owner)
        weak = make_item(self.other, title='Rak plastik', description='rak', category='home')
        post = make_post(self.buyer)
        found = suggest_items_for_wanted(post)
        self.assertEqual(found[0].item, best)
        self.assertGreaterEqual(found[0].score, found[-1].score)
        self.assertEqual(suggest_wanted_for_item(best)[0].wanted_post, post)
        self.assertNotIn(weak, [m.item for m in found[:1]])

    def test_suggestion_pages_restricted_to_owners(self):
        item, post = make_item(self.owner), make_post(self.buyer)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('item_matching:item_suggestions', args=[item.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('item_matching:wanted_suggestions', args=[post.pk])).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('item_matching:item_suggestions', args=[item.pk])).status_code, 200)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('item_matching:wanted_suggestions', args=[post.pk])).status_code, 200)


class DashboardTests(Base):
    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse('item_matching:dashboard')).status_code, 302)

    def test_tabs_show_only_own_rows(self):
        item = make_item(self.owner)
        ItemRequest.objects.create(item=item, requester=self.buyer)
        self.client.force_login(self.owner)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'incoming'})
        self.assertEqual(len(r.context['rows']), 1)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'sent'})
        self.assertEqual(len(r.context['rows']), 0)
        self.client.force_login(self.other)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'incoming'})
        self.assertEqual(len(r.context['rows']), 0)

    def test_invalid_tab_falls_back(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'nope'})
        self.assertEqual(r.context['tab'], 'incoming')


