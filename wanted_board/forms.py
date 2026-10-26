from django import forms

from .models import Offer, WantedPost


class WantedPostForm(forms.ModelForm):
    class Meta:
        model = WantedPost
        fields = (
            "title",
            "image",
            "description",
            "category",
            "listing_type",
            "preferred_condition",
            "budget",
            "location",
        )
        labels = {
            "title": "Item you are looking for",
            "image": "Reference picture",
            "description": "What do you need?",
            "category": "Category",
            "listing_type": "Offer type",
            "preferred_condition": "Preferred condition",
            "budget": "Maximum budget",
            "location": "Your location",
        }
        help_texts = {
            "image": "This picture is for reference only. Upload a JPG, JPEG, PNG, or WEBP image.",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Example: Study desk lamp"}
            ),
            "image": forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp"}),
            "description": forms.Textarea(
                attrs={
                    "placeholder": "Describe the item, specifications, or details you need.",
                    "rows": 5,
                }
            ),
            "budget": forms.NumberInput(
                attrs={"min": 0, "step": 1000, "placeholder": "150000"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Example: Kukusan or UI Campus"}
            ),
        }


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ("offered_price",)
        labels = {
            "offered_price": "Your offer price",
        }
        widgets = {
            "offered_price": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1000,
                    "placeholder": "125000",
                    "inputmode": "numeric",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["offered_price"].required = True
