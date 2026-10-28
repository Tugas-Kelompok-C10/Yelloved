from django import forms

from .models import Offer, WantedPost


class WantedPostForm(forms.ModelForm):
    class Meta:
        model = WantedPost
        fields = (
            "title",
            "description",
            "category",
            "budget",
            "location",
        )
        labels = {
            "title": "Item you are looking for",
            "description": "What do you need?",
            "category": "Category",
            "budget": "Maximum budget",
            "location": "Your location",
        }
        error_messages = {
            "budget": {
                "required": "Please enter a maximum budget greater than Rp0.",
                "min_value": "Please enter a maximum budget greater than Rp0.",
            },
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
                attrs={"min": "0.01", "step": "0.01", "placeholder": "150000",
                       "data-wanted-budget": ""}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Example: Kukusan or UI Campus"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        provided_initial = kwargs.get("initial", {})
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance._state.adding and user and user.is_authenticated:
            address = user.saved_addresses.first()
            if address and "location" not in provided_initial:
                # Use the general area, never the private street address.
                location = ", ".join(part for part in (address.city, address.province) if part)
                self.initial["location"] = location if len(location) <= 120 else address.city
        self.fields["location"].help_text = (
            "Prefilled from your profile's main address when available. You can edit it for this request."
        )


class WantedCreateForm(WantedPostForm):
    creation_token = forms.CharField(widget=forms.HiddenInput)


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
