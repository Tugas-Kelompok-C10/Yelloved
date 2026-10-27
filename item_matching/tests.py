from decimal import Decimal

from django.contrib.auth import get_user_model
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
                budget=Decimal('100000'), location='Kukusan', image='wanted_references/x.png')
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
        self.client.post(url, {'message': 'mau'})
        self.assertEqual(ItemRequest.objects.count(), 1)
        r = self.client.post(url, {'message': 'lagi'})
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
        self.assertEqual(self.post.status, WantedPost.Status.FULFILLED)
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


class MatchingScoreTests(Base):
    def test_matching_item_scores_and_explains(self):
        m = evaluate(make_item(self.owner), make_post(self.buyer))
        self.assertIsNotNone(m)
        self.assertIn('Kategori sama', m.reasons)

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


# ---------------------------------------------------------------------------
# Integration with the items, wanted_board, account_profile and transactions apps
# ---------------------------------------------------------------------------
from account_profile.models import NotificationPreference, Profile  # noqa: E402

from .contacts import contact_for, whatsapp_url  # noqa: E402


class CrossAppConsistencyTests(Base):
    def test_owner_marking_item_sold_in_items_app_resolves_dependants(self):
        item = make_item(self.owner)
        mine = make_item(self.buyer, title='Tas')
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        swap_req = ItemRequest.objects.create(item=make_item(self.other, listing_type='swap', price=None),
                                              requester=self.buyer, offered_item=mine)
        offer = ItemOffer.objects.create(wanted_post=make_post(self.other), item=mine, offerer=self.buyer)
        item.status = Item.Status.SOLD
        item.save()                       # what the items edit form does
        req.refresh_from_db()
        self.assertEqual(req.status, 'rejected')
        mine.status = Item.Status.UNAVAILABLE
        mine.save()
        swap_req.refresh_from_db(); offer.refresh_from_db()
        self.assertEqual(swap_req.status, 'cancelled')
        self.assertEqual(offer.status, 'withdrawn')

    def test_saving_available_item_leaves_pending_requests_alone(self):
        item = make_item(self.owner)
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        item.title = 'Lampu baru'
        item.save()
        req.refresh_from_db()
        self.assertEqual(req.status, 'pending')

    def test_closing_wanted_post_rejects_pending_item_offers(self):
        post = make_post(self.buyer)
        offer = ItemOffer.objects.create(wanted_post=post, item=make_item(self.owner), offerer=self.owner)
        post.status = WantedPost.Status.FULFILLED     # wanted_board.update_status does this
        post.save(update_fields=['status', 'updated_at'])
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'rejected')

    def test_deleted_swap_item_blocks_acceptance(self):
        swap = make_item(self.owner, listing_type='swap', price=None)
        mine = make_item(self.buyer, title='Tas')
        req = ItemRequest.objects.create(item=swap, requester=self.buyer, offered_item=mine)
        mine.delete()
        with self.assertRaises(MatchingError):
            services.accept_request(req.pk, self.owner)


class ContactTests(Base):
    def test_whatsapp_normalisation(self):
        self.assertEqual(whatsapp_url('0812-3456-7890'), 'https://wa.me/6281234567890')
        self.assertEqual(whatsapp_url('+62 812 3456 7890'), 'https://wa.me/6281234567890')
        self.assertEqual(whatsapp_url('812345678'), 'https://wa.me/62812345678')
        self.assertEqual(whatsapp_url('123'), '')
        self.assertEqual(whatsapp_url(''), '')

    def test_contact_for_handles_missing_profile_and_phone(self):
        self.assertIsNone(contact_for(self.owner))
        Profile.objects.create(user=self.owner)
        self.assertIsNone(contact_for(self.owner))
        Profile.objects.filter(user=self.owner).update(phone_number='08123456789')
        self.assertEqual(contact_for(User.objects.get(pk=self.owner.pk))['phone'], '08123456789')

    def test_contact_revealed_only_after_acceptance_and_only_to_parties(self):
        Profile.objects.create(user=self.owner, phone_number='081111111111')
        Profile.objects.create(user=self.buyer, phone_number='082222222222')
        item = make_item(self.owner)
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        dash = reverse('item_matching:dashboard')
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get(dash, {'tab': 'sent'}), '081111111111')
        services.accept_request(req.pk, self.owner)
        self.assertContains(self.client.get(dash, {'tab': 'sent'}), '081111111111')
        self.assertContains(self.client.get(dash, {'tab': 'sent'}), reverse('transactions:checkout'))
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(dash, {'tab': 'incoming'}), '082222222222')
        self.client.force_login(self.other)
        body = self.client.get(dash, {'tab': 'sent'}).content.decode()
        self.assertNotIn('081111111111', body)
        self.assertNotIn('082222222222', body)

    def test_free_item_has_no_checkout_link(self):
        item = make_item(self.owner, listing_type='free', price=None)
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        services.accept_request(req.pk, self.owner)
        self.client.force_login(self.buyer)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'sent'})
        self.assertNotContains(r, reverse('transactions:checkout'))
        self.assertContains(r, reverse('transactions:pesan'))


class DetailPagesIntegrationTests(Base):
    def test_item_detail_shows_request_state_to_requester_and_owner(self):
        item = make_item(self.owner)
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        self.client.force_login(self.buyer)
        r = self.client.get(item.get_absolute_url())
        self.assertContains(r, reverse('item_matching:request_cancel', args=[req.pk]))
        self.client.force_login(self.owner)
        r = self.client.get(item.get_absolute_url())
        self.assertContains(r, '1 request menunggu')
        self.assertContains(r, reverse('item_matching:item_suggestions', args=[item.pk]))
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(item.get_absolute_url()), '1 request menunggu')

    def test_wanted_detail_page_is_left_to_the_wanted_board_team(self):
        """The wanted board deliberately keeps item_matching UI off its detail page."""
        post = make_post(self.buyer)
        ItemOffer.objects.create(wanted_post=post, item=make_item(self.owner), offerer=self.owner)
        url = reverse('wanted_board:wanted_detail', args=[post.pk])
        for user in (self.buyer, self.owner, self.other):
            self.client.force_login(user)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'item-matching/wanted/')
            self.assertNotContains(r, 'Suggested items')

    def test_offers_are_handled_from_the_dashboard_and_item_page(self):
        post = make_post(self.buyer)
        offer = ItemOffer.objects.create(wanted_post=post, item=make_item(self.owner), offerer=self.owner,
                                         message='kondisi mulus')
        self.client.force_login(self.buyer)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_received'})
        self.assertContains(r, 'kondisi mulus')
        self.assertContains(r, reverse('item_matching:offer_accept', args=[offer.pk]))
        self.client.force_login(self.owner)
        r = self.client.get(reverse('item_matching:dashboard'), {'tab': 'offers_sent'})
        self.assertContains(r, reverse('item_matching:offer_withdraw', args=[offer.pk]))
        self.assertNotContains(r, reverse('item_matching:offer_accept', args=[offer.pk]))
        # the owner of an item reaches the offer form through the item's suggestions page
        item = offer.item
        self.assertContains(self.client.get(item.get_absolute_url()),
                            reverse('item_matching:item_suggestions', args=[item.pk]))
        r = self.client.get(reverse('item_matching:item_suggestions', args=[item.pk]))
        self.assertContains(r, reverse('item_matching:offer_create', args=[post.pk]))

    def test_action_returns_to_the_originating_page_and_blocks_open_redirects(self):
        item = make_item(self.owner)
        req = ItemRequest.objects.create(item=item, requester=self.buyer)
        req2 = ItemRequest.objects.create(item=item, requester=self.other)
        self.client.force_login(self.buyer)
        r = self.client.post(reverse('item_matching:request_cancel', args=[req.pk]),
                             {'next': item.get_absolute_url()})
        self.assertRedirects(r, item.get_absolute_url())
        self.client.force_login(self.other)
        r = self.client.post(reverse('item_matching:request_cancel', args=[req2.pk]),
                             {'next': 'https://evil.example/x'})
        self.assertTrue(r['Location'].startswith(reverse('item_matching:dashboard')))


class NotificationTests(Base):
    def setUp(self):
        super().setUp()
        self.item = make_item(self.owner)
        ItemRequest.objects.create(item=self.item, requester=self.buyer)
        self.post = make_post(self.buyer)
        ItemOffer.objects.create(wanted_post=self.post, item=make_item(self.other), offerer=self.other)

    def page(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('show_main'))

    def test_pending_work_shows_in_navbar_popover_and_badge(self):
        r = self.page(self.owner)
        self.assertEqual(r.context['matching_pending_count'], 1)
        self.assertContains(r, '1 request barang menunggu keputusanmu')
        r = self.page(self.buyer)
        self.assertContains(r, '1 penawaran barang untuk wanted post-mu')

    def test_decisions_notify_the_other_party(self):
        req = ItemRequest.objects.get()
        services.accept_request(req.pk, self.owner)
        self.assertContains(self.page(self.buyer), 'diterima')

    def test_preferences_silence_the_matching_notification_group(self):
        NotificationPreference.objects.create(user=self.owner, order_updates=False)
        NotificationPreference.objects.create(user=self.buyer, wanted_updates=False)
        r = self.page(self.owner)
        self.assertNotContains(r, 'request barang menunggu')
        self.assertEqual(r.context['matching_pending_count'], 1)     # badge stays: it needs action
        self.assertNotContains(self.page(self.buyer), 'penawaran barang untuk wanted post-mu')

    def test_anonymous_and_idle_users_get_empty_state(self):
        self.client.logout()
        r = self.client.get(reverse('show_main'))
        self.assertNotIn('matching_notifications', r.context)
        self.assertContains(self.page(User.objects.create_user('idle', password='pw')), 'Belum ada notifikasi')


# ---------------------------------------------------------------------------
# UI: transaction-style dashboard, tab descriptions, navbar icon + summary popover
# ---------------------------------------------------------------------------
from django.test import RequestFactory  # noqa: E402

from .context_processors import matching_notifications  # noqa: E402
from .tabs import TABS  # noqa: E402


class DashboardLayoutTests(Base):
    def setUp(self):
        super().setUp()
        self.item = make_item(self.owner)
        self.req = ItemRequest.objects.create(item=self.item, requester=self.buyer, message='halo kak')
        self.url = reverse('item_matching:dashboard')

    def test_uses_transaction_page_box_layout(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.url)
        for cls in ('container orders-page', 'orders-heading', 'orders-tabs', 'order-card',
                    'order-card-top', 'order-card-body', 'order-card-footer'):
            self.assertContains(r, cls)
        self.assertNotContains(r, 'matching-card')

    def test_each_tab_shows_its_own_description_under_the_tab_title(self):
        self.client.force_login(self.owner)
        for tab in TABS:
            r = self.client.get(self.url, {'tab': tab['key']})
            self.assertEqual(r.context['active']['key'], tab['key'])
            self.assertContains(r, f'<h2 id="matching-tab-title">{tab["label"]}</h2>', html=False)
            self.assertContains(r, tab['description'])
            for other in TABS:
                if other['key'] != tab['key']:
                    self.assertNotContains(r, other['description'])

    def test_tab_counts_and_badges(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.url)
        incoming = next(t for t in r.context['tabs'] if t['key'] == 'incoming')
        self.assertEqual((incoming['total'], incoming['pending']), (1, 1))
        self.assertContains(r, '1 data · 1 menunggu')

    def test_empty_tab_keeps_empty_state_with_tab_specific_hint(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.url, {'tab': 'offers_sent'})
        self.assertContains(r, 'Belum Ada Pesanan.')
        self.assertContains(r, next(t for t in TABS if t['key'] == 'offers_sent')['empty'])

    def test_card_shows_item_message_status_and_actions_in_footer(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.url)
        self.assertContains(r, 'RQ-%04d' % self.req.pk)
        self.assertContains(r, 'halo kak')
        self.assertContains(r, 'Status: Menunggu')
        self.assertContains(r, reverse('item_matching:request_accept', args=[self.req.pk]))
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(self.url, {'tab': 'sent'}),
                            reverse('item_matching:request_cancel', args=[self.req.pk]))


class NavbarIconTests(Base):
    def page(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('show_main'))

    def test_text_link_is_replaced_by_icon_with_popover(self):
        r = self.page(self.owner)
        self.assertContains(r, 'nav-matching-trigger')
        self.assertContains(r, 'id="matching-popover"')
        self.assertNotContains(r, '>Item Matching</a>')
        self.assertNotContains(r, '>Matching</a>')

    def test_anonymous_users_get_no_icon(self):
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('show_main')), 'nav-matching-trigger')

    def test_popover_summarises_all_four_groups(self):
        item = make_item(self.owner)
        ItemRequest.objects.create(item=item, requester=self.buyer)
        r = self.page(self.owner)
        summary = r.context['matching_summary']
        self.assertEqual([t['key'] for t in summary['tabs']],
                         ['incoming', 'sent', 'offers_received', 'offers_sent'])
        self.assertEqual((summary['total'], summary['action_needed'], summary['waiting']), (1, 1, 0))
        for tab in TABS:
            self.assertContains(r, tab['short'])
        self.assertContains(r, '1 perlu tindakan')
        self.assertContains(r, 'nav-matching-badge')
        r = self.page(self.buyer)
        self.assertEqual(r.context['matching_summary']['waiting'], 1)
        self.assertContains(r, '1 menunggu')
        self.assertNotContains(r, 'nav-matching-badge')          # nothing for the buyer to act on

    def test_popover_empty_state_for_idle_user(self):
        r = self.page(self.other)
        self.assertEqual(r.context['matching_summary']['total'], 0)
        self.assertContains(r, 'Belum ada aktivitas')

    def test_badge_is_capped(self):
        for n in range(11):
            ItemRequest.objects.create(item=make_item(self.owner, title=f'Barang {n}'), requester=self.buyer)
        self.assertContains(self.page(self.owner), '9+')

    def test_context_processor_skips_admin_static_and_anonymous(self):
        rf = RequestFactory()
        for path in ('/admin/', '/static/css/x.css', '/media/a.png'):
            req = rf.get(path); req.user = self.owner
            self.assertEqual(matching_notifications(req), {})
        req = rf.get('/'); req.user = type('Anon', (), {'is_authenticated': False})()
        self.assertEqual(matching_notifications(req), {})

    def test_navbar_query_cost_is_bounded(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse('show_main'))
        ours = [q for q in ctx.captured_queries
                if 'item_matching_item' in q['sql'] or 'notificationpreference' in q['sql']]
        # 4 aggregate counts (one per tab) + notification preference + 2 recent-decision lists
        self.assertLessEqual(len(ours), 7)
