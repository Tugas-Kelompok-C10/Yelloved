from django import forms
from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'condition', 'listing_type', 'price', 'location', 'image', 'image_url', 'status']
        widgets = {'description': forms.Textarea(attrs={'rows': 5}),
                   'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
                   'image': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
                   'image_url': forms.HiddenInput()}
        help_texts = {'price': 'Dalam rupiah. Wajib untuk Jual; dikosongkan untuk Gratis/Tukar.',
                      'image': 'Pilih foto dari galeri atau penyimpanan perangkat (JPG, PNG, WebP; maksimal 5 MB).',
                      'location': 'Contoh: Kukusan, Depok. Hindari alamat rumah lengkap.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['image'].widget.attrs['required'] = True

    def clean(self):
        cleaned_data = super().clean()
        uploaded_image = cleaned_data.get('image')
        legacy_image_url = cleaned_data.get('image_url')
        existing_image = bool(self.instance.pk and (self.instance.image or self.instance.image_url))
        if not uploaded_image and not legacy_image_url and not existing_image:
            self.add_error('image', 'Pilih foto item dari galeri atau penyimpanan perangkat.')
        return cleaned_data


class ItemFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200)
    category = forms.ChoiceField(required=False, choices=[('', 'Semua kategori'), *Item.Category.choices])
    condition = forms.ChoiceField(required=False, choices=[('', 'Semua kondisi'), *Item.Condition.choices])
    listing_type = forms.ChoiceField(required=False, choices=[('', 'Semua tipe'), *Item.ListingType.choices])
    status = forms.ChoiceField(required=False, choices=[('', 'Semua status'), *Item.Status.choices])
