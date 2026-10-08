from django import forms

from .models import Offer, WantedPost


class WantedPostForm(forms.ModelForm):
    class Meta:
        model = WantedPost
        fields = (
            "title",
            "description",
            "category",
            "preferred_condition",
            "budget",
            "location",
        )
        labels = {
            "title": "Barang yang dicari",
            "description": "Deskripsi kebutuhan",
            "category": "Kategori",
            "preferred_condition": "Kondisi yang diinginkan",
            "budget": "Anggaran maksimal",
            "location": "Lokasi",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Contoh: Lampu meja belajar"}
            ),
            "description": forms.Textarea(
                attrs={
                    "placeholder": "Jelaskan spesifikasi atau detail barang yang kamu butuhkan.",
                    "rows": 5,
                }
            ),
            "budget": forms.NumberInput(
                attrs={"min": 0, "step": 1000, "placeholder": "150000"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Contoh: Kukusan atau Kampus UI"}
            ),
        }


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ("message", "offered_price")
        labels = {
            "message": "Pesan penawaran",
            "offered_price": "Harga yang ditawarkan",
        }
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Ceritakan kondisi barang dan cara menghubungimu.",
                    "rows": 4,
                }
            ),
            "offered_price": forms.NumberInput(
                attrs={"min": 0, "step": 1000, "placeholder": "125000"}
            ),
        }
