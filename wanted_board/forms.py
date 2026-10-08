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
            "title": "Item you are looking for",
            "description": "What do you need?",
            "category": "Category",
            "preferred_condition": "Preferred condition",
            "budget": "Maximum budget",
            "location": "Location",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Example: Study desk lamp"}
            ),
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
        fields = ("message", "offered_price")
        labels = {
            "message": "Offer message",
            "offered_price": "Offered price",
        }
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "placeholder": "Describe the item's condition and how to contact you.",
                    "rows": 4,
                }
            ),
            "offered_price": forms.NumberInput(
                attrs={"min": 0, "step": 1000, "placeholder": "125000"}
            ),
        }
