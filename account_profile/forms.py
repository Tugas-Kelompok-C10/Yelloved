from django import forms

from .models import Address, Profile


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Nama", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    class Meta:
        model = Profile
        fields = ("photo", "date_of_birth", "gender", "phone_number")
        labels = {
            "date_of_birth": "Tanggal Lahir",
            "gender": "Jenis kelamin",
            "phone_number": "Nomor HP",
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
        self.fields["first_name"].initial = user.first_name
        self.fields["email"].initial = user.email
        self.fields["gender"].choices = [("", "Belum diatur"), *Profile.GENDER_CHOICES]

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ukuran foto maksimal 5 MB.")
        header = photo.read(12)
        photo.seek(0)
        valid_image = (
            header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith((b"GIF87a", b"GIF89a"))
            or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
        )
        if not valid_image:
            raise forms.ValidationError("Pilih file gambar JPG, PNG, GIF, atau WebP.")
        return photo

    def save(self, commit=True):
        old_photo_name = self.instance.photo.name
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
    class Meta:
        model = Address
        fields = (
            "label", "recipient_name", "phone_number", "street_address",
            "city", "province", "postal_code", "is_default",
        )
        labels = {
            "label": "Label alamat",
            "recipient_name": "Nama penerima",
            "phone_number": "Nomor HP",
            "street_address": "Alamat lengkap",
            "city": "Kota / Kabupaten",
            "province": "Provinsi",
            "postal_code": "Kode pos",
            "is_default": "Jadikan alamat utama",
        }
        widgets = {
            "street_address": forms.Textarea(attrs={"rows": 3}),
        }
