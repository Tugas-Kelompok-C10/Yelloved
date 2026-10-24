from django import forms
from .models import Item


class ItemForm(forms.ModelForm):
    image_url = forms.URLField(label='URL foto', max_length=1000, required=True,
                               widget=forms.URLInput(attrs={'placeholder': 'https://…'}))
    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'condition', 'listing_type', 'price', 'location', 'image_url', 'status']
        widgets = {'description': forms.Textarea(attrs={'rows': 5}),
                   'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
                   'image_url': forms.URLInput(attrs={'placeholder': 'https://…'})}
        help_texts = {'price': 'Dalam rupiah. Wajib untuk Jual; dikosongkan untuk Gratis/Tukar.',
                      'image_url': 'Gunakan tautan langsung foto HTTP/HTTPS.',
                      'location': 'Contoh: Kukusan, Depok. Hindari alamat rumah lengkap.'}


class ItemFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200)
    category = forms.ChoiceField(required=False, choices=[('', 'Semua kategori'), *Item.Category.choices])
    condition = forms.ChoiceField(required=False, choices=[('', 'Semua kondisi'), *Item.Condition.choices])
    listing_type = forms.ChoiceField(required=False, choices=[('', 'Semua tipe'), *Item.ListingType.choices])
    status = forms.ChoiceField(required=False, choices=[('', 'Semua status'), *Item.Status.choices])
