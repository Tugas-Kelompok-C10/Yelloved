from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from items.models import Item
from wanted_board.models import WantedPost

from . import services
from .contacts import contact_for
from .forms import ItemOfferForm, ItemRequestForm, PhotoOfferForm
from wanted_board.locking import locked_wanted_post
from chat.session import session_guard
from .matching import evaluate, suggest_items_for_wanted, suggest_wanted_for_item
from .models import ItemOffer, ItemRequest
from .services import MatchingError
from .summary import tabs_with_stats
from .tabs import TAB_KEYS
from .rate_limits import (PhotoOfferRateLimited, check_photo_offer_limit,
                          locked_photo_offer_quota, record_photo_offer)


@login_required(login_url='login')
@require_GET
def dashboard(request):
    tab = request.GET.get('tab', 'incoming')
    if tab not in TAB_KEYS:
        tab = 'incoming'
    user = request.user
    requests_qs = ItemRequest.objects.select_related('item', 'offered_item', 'requester', 'item__owner')
    offers_qs = ItemOffer.objects.select_related('item', 'wanted_post', 'wanted_post__requester', 'offerer', 'matched_transaction')
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
        row.activity_title = row.item.title if row.item_id else row.wanted_post.title
        row.activity_image = row.item.display_image_url if row.item_id else row.display_image_url
        row.activity_url = row.item.get_absolute_url() if row.item_id else reverse('wanted_board:wanted_detail', args=[row.wanted_post_id])
        row.activity_price = row.item.price_display if tab in ('incoming', 'sent') else row.price_display
        # Contact details are revealed only to the two parties, and only once a match is accepted.
        if row.status == 'accepted':
            other = {'incoming': lambda r: r.requester, 'sent': lambda r: r.item.owner,
                     'offers_received': lambda r: r.offerer,
                     'offers_sent': lambda r: r.wanted_post.requester}[tab](row)
            row.counterpart = other
            row.contact = contact_for(other) if other else None
            # Paid items continue to the checkout page; free/swap items only need the handover.
            row.checkout = tab in ('sent', 'offers_received') and row.item_id and row.item.listing_type == Item.ListingType.SALE
    return render(request, 'item_matching/dashboard.html', {
        'name': 'Yelloved', 'tab': tab, 'rows': rows, 'tabs': tabs, 'active': active,
        'is_request_tab': tab in ('incoming', 'sent'),
    })


@require_POST
def photo_offer_create(request, wanted_id):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Please sign in before sending an offer.'}, status=401)
    if request.headers.get('X-Offer-User') != str(request.user.pk):
        return JsonResponse({'message': 'Your account changed. Reload this page before sending an offer.'}, status=409)
    import uuid
    try:
        token = uuid.UUID(request.POST.get('submission_id', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'message': 'Reload the offer form before sending.'}, status=422)
    offer = None
    try:
        with locked_photo_offer_quota(request.user) as quota, locked_wanted_post(wanted_id) as post:
            previous = ItemOffer.objects.filter(submission_id=token).first()
            if previous:
                if previous.offerer_id != request.user.pk or previous.wanted_post_id != post.pk:
                    return JsonResponse({'message': 'This offer token is unavailable. Reopen the form.'}, status=409)
                return JsonResponse({'message': 'Your offer was already sent.', 'id': previous.pk})
            if post.requester_id == request.user.pk:
                return JsonResponse({'message': 'You cannot offer an item on your own wanted post.'}, status=403)
            if post.status != WantedPost.Status.OPEN:
                return JsonResponse({'message': 'This wanted post is no longer accepting offers.'}, status=409)
            form = PhotoOfferForm(request.POST, request.FILES)
            if not form.is_valid():
                return JsonResponse({'message': next(iter(form.errors.values()))[0], 'errors': form.errors.get_json_data()}, status=422)
            check_photo_offer_limit(quota)
            offer = ItemOffer(wanted_post=post, offerer=request.user, photo=form.cleaned_data['image'],
                              offered_price=form.cleaned_data['price'], message=form.cleaned_data['description'], submission_id=token)
            offer.full_clean()
            offer.save()
            record_photo_offer(quota)
    except PhotoOfferRateLimited as error:
        response = JsonResponse({'code': 'rate_limited', 'message': error.message,
                                 'retry_after': error.retry_after}, status=429)
        response['Retry-After'] = str(error.retry_after)
        return response
    except (OSError, IntegrityError, ValidationError):
        if offer and offer.photo and getattr(offer.photo, '_committed', False):
            try:
                offer.photo.storage.delete(offer.photo.name)
            except OSError:
                pass
        return JsonResponse({'message': 'Your offer could not be saved. Please retry with the same form.'}, status=503)
    return JsonResponse({'message': 'Your offer was sent. You can track it in Activity → Sent Offers.', 'id': offer.pk}, status=201)


@require_GET
@session_guard
def activity_preview(request):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Please sign in again.'}, status=401)
    from .context_processors import activity_summary
    data = activity_summary(request)
    response = JsonResponse({'html': render_to_string('item_matching/_preview.html', data, request=request),
                             'pending': data['matching_pending_count']})
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def request_create(request, item_id):
    item = get_object_or_404(Item.objects.select_related('owner'), pk=item_id)
    if item.owner_id is None or item.source != 'user':
        messages.error(request, 'Inspiration catalog items cannot be requested.')
        return redirect(item)
    if item.owner_id == request.user.pk:
        messages.error(request, 'You cannot request your own item.')
        return redirect(item)
    if item.status != Item.Status.AVAILABLE:
        messages.error(request, 'This item is no longer available.')
        return redirect(item)
    form = ItemRequestForm(request.POST if request.method == 'POST' else None, item=item, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your request was sent to the item owner.')
        return _dashboard_redirect('sent')
    return render(request, 'item_matching/request_form.html', {'name': 'Yelloved', 'form': form, 'item': item})


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def offer_create(request, wanted_id):
    post = get_object_or_404(WantedPost.objects.select_related('requester'), pk=wanted_id)
    if post.requester_id == request.user.pk:
        messages.error(request, 'Cannot offer on your own post.')
        return redirect('wanted_board:wanted_detail', pk=post.pk)
    if post.status != WantedPost.Status.OPEN:
        messages.error(request, 'This wanted post is no longer accepting offers.')
        return redirect('wanted_board:wanted_detail', pk=post.pk)
    form = ItemOfferForm(request.POST if request.method == 'POST' else None, wanted_post=post, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your item offer was sent.')
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
    return _act(request, services.accept_request, pk, 'incoming', 'Request accepted. The item is now marked unavailable.')


@login_required(login_url='login')
@require_POST
def request_reject(request, pk):
    get_object_or_404(ItemRequest, pk=pk)
    return _act(request, services.reject_request, pk, 'incoming', 'Request rejected.')


@login_required(login_url='login')
@require_POST
def request_cancel(request, pk):
    get_object_or_404(ItemRequest, pk=pk)
    return _act(request, services.cancel_request, pk, 'sent', 'Request cancelled.')


@login_required(login_url='login')
@require_POST
def offer_accept(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.accept_offer, pk, 'offers_received',
                'Offer accepted. Continue to Transaction to arrange the handover.')


@login_required(login_url='login')
@require_POST
def offer_reject(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.reject_offer, pk, 'offers_received', 'Offer rejected.')


@login_required(login_url='login')
@require_POST
def offer_withdraw(request, pk):
    get_object_or_404(ItemOffer, pk=pk)
    return _act(request, services.withdraw_offer, pk, 'offers_sent', 'Offer withdrawn.')


@login_required(login_url='login')
@require_GET
def wanted_suggestions(request, pk):
    post = get_object_or_404(WantedPost.objects.select_related('requester'), pk=pk)
    if post.requester_id != request.user.pk:
        raise PermissionDenied('Only the wanted post owner can view these suggestions.')
    return render(request, 'item_matching/suggestions.html', {
        'name': 'Yelloved', 'mode': 'wanted', 'wanted_post': post,
        'matches': suggest_items_for_wanted(post)})


@login_required(login_url='login')
@require_GET
def item_suggestions(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.owner_id != request.user.pk:
        raise PermissionDenied('Only the item owner can view these suggestions.')
    return render(request, 'item_matching/suggestions.html', {
        'name': 'Yelloved', 'mode': 'item', 'item': item,
        'matches': suggest_wanted_for_item(item)})
