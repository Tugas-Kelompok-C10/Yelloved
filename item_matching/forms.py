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
            'offer_price': forms.NumberInput(attrs={'min': 1, 'step': 1000, 'placeholder': 'Contoh: 45000'}),
            'message': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Perkenalkan diri dan sebutkan waktu/lokasi COD yang kamu inginkan.'}),
        }
        help_texts = {'offered_item': 'Wajib untuk listing bertipe Tukar.',
                      'offer_price': 'Nominal dalam Rupiah. Wajib untuk listing bertipe Jual.'}

    def __init__(self, *args, item, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Bound before validation so ItemRequest.clean() can see item and requester.
        self.instance.item = item
        self.instance.requester = user
        if item.listing_type == Item.ListingType.SWAP:
            self.fields['offered_item'].queryset = _own_available_items(user)
            self.fields['offered_item'].required = True
            self.fields['offered_item'].empty_label = 'Pilih barangmu'
        else:
            del self.fields['offered_item']
        if item.listing_type == Item.ListingType.SALE:
            self.fields['offer_price'].required = True
        else:
            # Barang gratis/tukar tidak punya harga, jadi tidak ada yang ditawar.
            del self.fields['offer_price']


class ItemOfferForm(forms.ModelForm):
    class Meta:
        model = ItemOffer
        fields = ('item', 'message')
        labels = {'item': 'Barang yang ditawarkan'}
        widgets = {'message': forms.Textarea(attrs={
            'rows': 4, 'placeholder': 'Jelaskan kondisi barang dan cara kamu bisa dihubungi.'})}

    def __init__(self, *args, wanted_post, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.wanted_post = wanted_post
        self.instance.offerer = user
        self.fields['item'].queryset = _own_available_items(user)
        self.fields['item'].empty_label = 'Pilih barangmu'
