from django import forms
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError
import warnings

from .models import Address, PaymentMethod, Profile, Review


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Name", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    class Meta:
        model = Profile
        fields = ("photo", "date_of_birth", "gender", "phone_number")
        labels = {
            "date_of_birth": "Date of birth",
            "gender": "Gender",
            "phone_number": "Phone number",
        }
        widgets = {
            "photo": forms.FileInput(attrs={
                "class": "profile-photo-input",
                "accept": "image/jpeg,image/png,image/gif,image/webp",
            }),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # ModelForm validation replaces instance.photo with the new upload.
        self.original_photo_name = self.instance.photo.name
        self.fields["first_name"].initial = user.first_name
        self.fields["email"].initial = user.email
        self.fields["gender"].choices = [("", "Not specified"), ("female", "Female"), ("male", "Male"), ("other", "Other")]
        self.fields["first_name"].widget.attrs.update(placeholder="Your name", autocomplete="given-name")
        self.fields["email"].widget.attrs.update(placeholder="you@example.com", autocomplete="email")
        self.fields["phone_number"].widget.attrs.update(placeholder="e.g. +62 812 3456 7890", autocomplete="tel", inputmode="tel")
        self.fields["date_of_birth"].widget.format = "%Y-%m-%d"

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo or not isinstance(photo, UploadedFile):
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Your photo must be 5 MB or smaller.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(photo) as image:
                    if image.format not in {"JPEG", "PNG", "GIF", "WEBP"}:
                        raise forms.ValidationError("Choose a JPG, PNG, GIF, or WEBP image.")
                    if max(image.size) > 4096:
                        raise forms.ValidationError("Your photo must be 4096 × 4096 pixels or smaller.")
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise forms.ValidationError("This photo could not be read. Choose a valid JPG, PNG, GIF, or WEBP image.")
        finally:
            photo.seek(0)
        return photo

    def save(self, commit=True):
        old_photo_name = self.original_photo_name
        profile = super().save(commit=False)
        profile.user = self.user
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save(update_fields=["first_name", "email"])
            profile.save()
            if old_photo_name and old_photo_name != profile.photo.name:
                profile.photo.storage.delete(old_photo_name)
        return profile


class AddressForm(forms.ModelForm):
    latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial.setdefault("latitude", self.instance.latitude)
            self.initial.setdefault("longitude", self.instance.longitude)
        self.fields["province"].required = True
        self.fields["postal_code"].required = True
        if not self.is_bound and self.instance._state.adding:
            self.initial["label"] = "Home"
        for name, placeholder in {"label": "e.g. Home or campus", "recipient_name": "Recipient's full name",
                                  "phone_number": "e.g. +62 812 3456 7890", "street_address": "Street, building, and unit",
                                  "city": "e.g. Depok", "province": "e.g. West Java", "postal_code": "Postal code"}.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder

    class Meta:
        model = Address
        fields = (
            "label", "recipient_name", "phone_number", "street_address",
            "city", "province", "postal_code", "is_default",
        )
        labels = {
            "label": "Address label",
            "recipient_name": "Recipient name",
            "phone_number": "Phone number",
            "street_address": "Street address",
            "city": "City",
            "province": "Province",
            "postal_code": "Postal code",
            "is_default": "Set as default address",
        }
        widgets = {
            "street_address": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if (latitude is None) != (longitude is None):
            raise forms.ValidationError("Both map coordinates are required.")
        if latitude is not None and not (-90 <= latitude <= 90):
            self.add_error("latitude", "Choose a valid map location.")
        if longitude is not None and not (-180 <= longitude <= 180):
            self.add_error("longitude", "Choose a valid map location.")
        return cleaned

    def save(self, commit=True):
        address = super().save(commit=False)
        address.latitude = self.cleaned_data.get("latitude")
        address.longitude = self.cleaned_data.get("longitude")
        if commit:
            address.save()
            self.save_m2m()
        return address


class PaymentMethodForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method_type"].choices = [("", "Choose a payment type"), ("bank", "Bank transfer"), ("e_wallet", "E-wallet")]
        for name, placeholder in {"provider": "e.g. BCA or GoPay", "account_name": "Name on the account",
                                  "account_identifier": "Account or phone number"}.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder

    class Meta:
        model = PaymentMethod
        fields = ("method_type", "provider", "account_name", "account_identifier", "is_default")
        labels = {
            "method_type": "Payment type",
            "provider": "Bank or e-wallet provider",
            "account_name": "Account holder",
            "account_identifier": "Account or phone number",
            "is_default": "Set as default payment method",
        }




class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(n, f'{n} star' if n == 1 else f'{n} stars') for n in range(1, 6)], coerce=int)

    class Meta:
        model = Review
        fields = ['seller', 'rating', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'maxlength': 2000})}
        labels = {'seller': 'Seller', 'rating': 'Rating', 'comment': 'Comment (optional)'}

    def __init__(self, *args, transaction, user, **kwargs):
        from django.contrib.auth import get_user_model
        super().__init__(*args, **kwargs)
        self.instance.transaction = transaction
        self.instance.reviewer = user
        self.fields['seller'].queryset = get_user_model().objects.filter(
            pk__in=transaction.review_items.values_list('seller_id', flat=True),
        ).exclude(pk=user.pk).distinct()
        if self.fields['seller'].queryset.count() == 1:
            self.fields['seller'].initial = self.fields['seller'].queryset.first()
