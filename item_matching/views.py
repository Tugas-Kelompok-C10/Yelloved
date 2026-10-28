from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from items.models import Item
from wanted_board.models import WantedPost

from . import services
from .contacts import contact_for
from .forms import ItemOfferForm, ItemRequestForm
from .matching import evaluate, suggest_items_for_wanted, suggest_wanted_for_item
from .models import ItemOffer, ItemRequest
from .services import MatchingError
from .summary import tabs_with_stats
from .tabs import TAB_KEYS


@login_required(login_url='login')
@require_GET
def dashboard(request):
    tab = request.GET.get('tab', 'incoming')
    if tab not in TAB_KEYS:
        tab = 'incoming'
    user = request.user
    requests_qs = ItemRequest.objects.select_related('item', 'offered_item', 'requester', 'item__owner')
    offers_qs = ItemOffer.objects.select_related('item', 'wanted_post', 'wanted_post__requester', 'offerer')
    data = {
        'incoming': requests_qs.filter(item__owner=user),
        'sent': requests_qs.filter(requester=user),
        'offers_received': offers_qs.filter(wanted_post__requester=user),
        'offers_sent': offers_qs.filter(offerer=user),
    }
    tabs = tabs_with_stats(user)
    active = next(t for t in tabs if t['key'] == tab)
    rows = list(data[tab])
    for row in rows:
        # Contact details are revealed only to the two parties, and only once a match is accepted.
        if row.status == 'accepted':
            other = {'incoming': lambda r: r.requester, 'sent': lambda r: r.item.owner,
                     'offers_received': lambda r: r.offerer,
                     'offers_sent': lambda r: r.wanted_post.requester}[tab](row)
            row.counterpart = other
            row.contact = contact_for(other) if other else None
            # Paid items continue to the checkout page; free/swap items only need the handover.
            row.checkout = tab in ('sent', 'offers_received') and row.item.listing_type == Item.ListingType.SALE
    return render(request, 'item_matching/dashboard.html', {
        'name': 'Yelloved', 'tab': tab, 'rows': rows, 'tabs': tabs, 'active': active,
        'is_request_tab': tab in ('incoming', 'sent'),
    })


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def request_create(request, item_id):
    item = get_object_or_404(Item.objects.select_related('owner'), pk=item_id)
    if item.owner_id is None or item.source != 'user':
        messages.error(request, 'Barang katalog inspirasi tidak dapat direquest.')
        return redirect(item)
    if item.owner_id == request.user.pk:
        messages.error(request, 'Kamu tidak bisa merequest barangmu sendiri.')
        return redirect(item)
    if item.status != Item.Status.AVAILABLE:
        messages.error(request, 'Barang ini sudah tidak tersedia.')
        return redirect(item)
    form = ItemRequestForm(request.POST if request.method == 'POST' else None, item=item, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Request berhasil dikirim ke pemilik barang.')
        return _dashboard_redirect('sent')
    return render(request, 'item_matching/request_form.html', {'name': 'Yelloved', 'form': form, 'item': item})


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def offer_create(request, wanted_id):
    post = get_object_or_404(WantedPost.objects.select_related('requester'), pk=wanted_id)
    if post.requester_id == request.user.pk:
        messages.error(request, 'Kamu tidak bisa menawarkan barang ke wanted post milikmu sendiri.')
        return redirect('wanted_board:wanted_detail', pk=post.pk)
    if post.status != WantedPost.Status.OPEN:
        messages.error(request, 'Wanted post ini tidak lagi menerima penawaran.')
        return redirect('wanted_board:wanted_detail', pk=post.pk)
    form = ItemOfferForm(request.POST if request.method == 'POST' else None, wanted_post=post, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Penawaran barang berhasil dikirim.')
        return _dashboard_redirect('offers_sent')
    fits = {}
    for candidate in form.fields['item'].queryset:
        match = evaluate(candidate, post)
        if match:
            fits[candidate.pk] = match
    return render(request, 'item_matching/offer_form.html', {
        'name': 'Yelloved', 'form': form, 'wanted_post': post,
        'fits': sorted(fits.values(), key=lambda m: -m.score)})


def _dashboard_redirect(tab):
    return redirect(f"{reverse('item_matching:dashboard')}?tab={tab}")


def _act(request, func, object_id, tab, success):
    try:
        func(object_id, request.user)
    except MatchingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, success)
    # Return to the page the action was taken from (item/wanted detail) when it is a safe local URL.
    target = request.POST.get('next', '')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return redirect(target)
    return _dashboard_redirect(tab)


@login_required(login_url='login')
@require_POST
def request_accept(request, pk):
    get_object_or_404(ItemRequest, pk=pk)
    return _act(request, services.accept_request, pk, 'incoming', 'Request diterima. Barang ditandai tidak tersedia.')


@login_required(login_url='login')
@require_POST
def request_reject(request, pk):
    get_object_or_404(ItemRequest, pk=pk)
    return _act(request, services.reject_request, pk, 'incoming', 'Request ditolak.')


@login_required(login_url='login')
@require_POST
def request_cancel(request, pk):
    get_object_or_404(ItemRequest, pk=pk)
    return _act(request, services.cancel_request, pk, 'sent', 'Request dibatalkan.')


@login_required(login_url='login')
@require_POST
def offer_accept(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.accept_offer, pk, 'offers_received',
                'Penawaran diterima. Wanted post ditandai terpenuhi.')


@login_required(login_url='login')
@require_POST
def offer_reject(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.reject_offer, pk, 'offers_received', 'Penawaran ditolak.')


@login_required(login_url='login')
@require_POST
def offer_withdraw(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.withdraw_offer, pk, 'offers_sent', 'Penawaran ditarik.')


@login_required(login_url='login')
@require_GET
def wanted_suggestions(request, pk):
    post = get_object_or_404(WantedPost.objects.select_related('requester'), pk=pk)
    if post.requester_id != request.user.pk:
        raise PermissionDenied('Hanya pembuat wanted post yang dapat melihat rekomendasi ini.')
    return render(request, 'item_matching/suggestions.html', {
        'name': 'Yelloved', 'mode': 'wanted', 'wanted_post': post,
        'matches': suggest_items_for_wanted(post)})


@login_required(login_url='login')
@require_GET
def item_suggestions(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.owner_id != request.user.pk:
        raise PermissionDenied('Hanya pemilik barang yang dapat melihat rekomendasi ini.')
    return render(request, 'item_matching/suggestions.html', {
        'name': 'Yelloved', 'mode': 'item', 'item': item,
        'matches': suggest_wanted_for_item(item)})
