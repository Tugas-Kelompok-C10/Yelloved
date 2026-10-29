from django import forms

from items.models import Item

from .models import ItemOffer, ItemRequest


def _own_available_items(user):
    return Item.objects.filter(owner=user, source='user', status=Item.Status.AVAILABLE).order_by('title')


class ItemRequestForm(forms.ModelForm):
    class Meta:
        model = ItemRequest
        fields = ('offered_item', 'offer_price', 'message')
        widgets = {
            'offer_price': forms.NumberInput(attrs={'min': 1, 'step': 1000, 'placeholder': '45000'}),
            'message': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Introduce yourself and suggest a time and place for the COD meet-up.'}),
        }
        help_texts = {'offered_item': 'Required for Swap listings.',
                      'offer_price': 'Amount in Rupiah. Required for Sale listings.'}

    def __init__(self, *args, item, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Bound before validation so ItemRequest.clean() can see item and requester.
        self.instance.item = item
        self.instance.requester = user
        if item.listing_type == Item.ListingType.SWAP:
            self.fields['offered_item'].queryset = _own_available_items(user)
            self.fields['offered_item'].required = True
            self.fields['offered_item'].empty_label = 'Choose your item'
        else:
            del self.fields['offered_item']
        if item.listing_type == Item.ListingType.SALE:
            self.fields['offer_price'].required = True
        else:
            # Free and swap items have no price, so there is nothing to offer.
            del self.fields['offer_price']


class ItemOfferForm(forms.ModelForm):
    class Meta:
        model = ItemOffer
        fields = ('item', 'message')
        labels = {'item': 'Item to offer'}
        widgets = {'message': forms.Textarea(attrs={
            'rows': 4, 'placeholder': 'Describe the condition of the item and how you can be contacted.'})}

    def __init__(self, *args, wanted_post, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.wanted_post = wanted_post
        self.instance.offerer = user
        self.fields['item'].queryset = _own_available_items(user)
        self.fields['item'].empty_label = 'Choose your item'
