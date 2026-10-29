from django import forms
from django.core.validators import FileExtensionValidator
from .validators import validate_item_upload
from .models import Item, ItemImage


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        uploads = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if len(uploads) > 5:
            raise forms.ValidationError('Add up to 5 photos per item.')
        result = []
        for upload in uploads:
            validate_item_upload(upload)
            cleaned = super().clean(upload, initial)
            if cleaned.image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise forms.ValidationError('Use JPG, PNG, or WebP photos only.')
            result.append(cleaned)
        return result


class ItemForm(forms.ModelForm):
    images = MultipleImageField(
        label='Item photos', required=False,
        widget=MultipleImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='Add up to 5 photos (JPG, PNG, or WebP, max 5 MB each).',
        validators=[FileExtensionValidator(allowed_extensions=('jpg', 'jpeg', 'png', 'webp'))],
    )
    delete_images = forms.ModelMultipleChoiceField(queryset=ItemImage.objects.none(), required=False,
                                                   widget=forms.MultipleHiddenInput)
    remove_legacy_image = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'condition', 'listing_type', 'price', 'location', 'image_url', 'status']
        widgets = {'description': forms.Textarea(attrs={'rows': 5}),
                   'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
                   'image_url': forms.HiddenInput()}
        help_texts = {'price': 'Dalam rupiah. Wajib untuk Jual; dikosongkan untuk Gratis/Tukar.',
                      'location': 'Contoh: Kukusan, Depok. Hindari alamat rumah lengkap.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_images = list(self.instance.images.all()) if self.instance.pk else []
        self.fields['delete_images'].queryset = self.instance.images.all() if self.instance.pk else ItemImage.objects.none()
        selected = {str(pk) for pk in (self['delete_images'].value() or [])}
        for image in self.existing_images:
            image.remove_selected = str(image.pk) in selected
        if not self.instance.pk:
            self.fields.pop('status')
        self.order_fields(['title', 'description', 'category', 'condition', 'listing_type', 'price', 'location', 'images', 'status', 'image_url', 'delete_images', 'remove_legacy_image'])

    def clean(self):
        cleaned = super().clean()
        remaining = len(self.existing_images) - len(cleaned.get('delete_images', []))
        if remaining + len(cleaned.get('images', [])) > 5:
            self.add_error('images', 'An item can have up to 5 photos. Remove an existing photo before adding more.')
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        if not self.instance.pk:
            item.status = Item.Status.AVAILABLE
        if commit:
            item.save()
            self.save_m2m()
            self.save_images(item)
        return item

    def save_images(self, item):
        for image in self.cleaned_data.get('delete_images', []):
            image.delete()
        existing = list(item.images.all())
        next_order = max((image.order for image in existing), default=-1) + 1
        for offset, upload in enumerate(self.cleaned_data.get('images', [])):
            ItemImage.objects.create(item=item, image=upload, order=next_order + offset)
        if self.cleaned_data.get('remove_legacy_image'):
            item.image_url = ''
        # Keep the old primary field compatible with consumers outside Items.
        first = item.images.order_by('order', 'pk').first()
        if first is None and self.cleaned_data.get('delete_images'):
            item.image_url = ''
        item.image = first.image.name if first else ''
        item.save(update_fields=['image', 'image_url'])
        item.__dict__.pop('primary_image', None)
        item._prefetched_objects_cache = {}


class ItemFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200)
    category = forms.ChoiceField(required=False, choices=[('', 'Semua kategori'), *Item.Category.choices])
    condition = forms.ChoiceField(required=False, choices=[('', 'Semua kondisi'), *Item.Condition.choices])
    listing_type = forms.ChoiceField(required=False, choices=[('', 'Semua tipe'), *Item.ListingType.choices])
    status = forms.ChoiceField(required=False, choices=[('', 'Semua status'), *Item.Status.choices])
