"""COD handover for an accepted wanted offer; catalogue checkout is unchanged."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from items.models import Item
from item_matching.models import ItemOffer
from wanted_board.locking import locked_wanted_post
from wanted_board.models import WantedPost
from .models import Transaction


class MeetupForm(forms.Form):
    location = forms.CharField(max_length=255, label='Meetup location')
    time = forms.DateTimeField(label='Meetup time', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def clean_time(self):
        value = self.cleaned_data['time']
        if value <= timezone.now():
            raise forms.ValidationError('Choose a meetup time in the future.')
        return value


@transaction.atomic
def update_handover(order_id, user, action, meetup=None):
    original = get_object_or_404(Transaction, order_id=order_id, accepted_offer__isnull=False)
    if user.pk not in (original.buyer_id, original.seller_id):
        raise PermissionDenied
    with locked_wanted_post(original.accepted_offer.wanted_post_id) as post:
        order = Transaction.objects.select_for_update().get(pk=original.pk)
        offer = ItemOffer.objects.select_for_update().get(pk=order.accepted_offer_id)
        if order.transaction_status in ('completed', 'cancelled'):
            raise ValidationError('This transaction has already ended. Reload to see its current status.')
        if post.status != WantedPost.Status.MATCHED or offer.status != ItemOffer.Status.ACCEPTED:
            raise ValidationError('This match has changed. Please reload before continuing.')
        if action == 'meetup':
            if user.pk != order.buyer_id:
                raise PermissionDenied
            order.cod_meeting_location = meetup['location']
            order.cod_meeting_time = meetup['time']
            order.transaction_status = 'processing'
        elif action == 'complete':
            if user.pk != order.buyer_id:
                raise PermissionDenied
            if order.transaction_status != 'processing':
                raise ValidationError('Save the meetup details before confirming receipt.')
            order.transaction_status = 'completed'
            order.payment_status = 'paid'  # Buyer confirms both receipt and COD payment.
            post.status = WantedPost.Status.FULFILLED
            if offer.item_id:
                Item.objects.filter(pk=offer.item_id).update(status=Item.Status.SOLD)
        elif action == 'cancel':
            order.transaction_status = 'cancelled'
            post.status = WantedPost.Status.OPEN
            offer.status = ItemOffer.Status.CANCELLED
            offer.save(update_fields=['status', 'updated_at'])
            if offer.item_id:
                Item.objects.filter(pk=offer.item_id, status=Item.Status.UNAVAILABLE).update(status=Item.Status.AVAILABLE)
        else:
            raise ValidationError('Choose a valid transaction action.')
        order.save(update_fields=['cod_meeting_location', 'cod_meeting_time', 'transaction_status', 'payment_status', 'updated_at'])
        post.save(update_fields=['status', 'updated_at'])
        return order


@login_required
@require_http_methods(['GET', 'POST'])
def wanted_detail(request, order_id):
    order = get_object_or_404(Transaction.objects.select_related('buyer', 'seller', 'accepted_offer__wanted_post'),
                              order_id=order_id, accepted_offer__isnull=False)
    if request.user.pk not in (order.buyer_id, order.seller_id):
        raise PermissionDenied
    form = MeetupForm(initial={'location': order.cod_meeting_location or order.shipping_address,
                                'time': order.cod_meeting_time})
    form.cleaned_data = {}  # The unbound meetup form can also display action errors.
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'meetup':
            form = MeetupForm(request.POST)
        if action in ('complete', 'cancel') and request.POST.get('confirm_received' if action == 'complete' else 'confirm_cancel') != 'on':
            form.add_error(None, 'Please confirm this action using the checkbox.')
        elif action != 'meetup' or form.is_valid():
            try:
                update_handover(order_id, request.user, action, form.cleaned_data if action == 'meetup' else None)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, {'meetup': 'Meetup details saved.', 'complete': 'Item received. Your wanted post is now fulfilled.',
                                          'cancel': 'Agreement cancelled. The wanted post is open again.'}[action])
                return redirect('transactions:wanted_detail', order_id=order_id)
    return render(request, 'transactions/wanted_detail.html', {
        'order': order, 'form': form, 'is_buyer': request.user.pk == order.buyer_id,
        'active': order.transaction_status not in ('completed', 'cancelled'),
        'price': 'Rp' + f'{order.total_amount:,.0f}'.replace(',', '.'),
    })
