from django import forms

from .models import Offer, WantedPost
from .validators import validate_reference_image


class ReferenceImageField(forms.ImageField):
    def to_python(self, data):
        if data is not None:
            validate_reference_image(data)
        return super().to_python(data)


class WantedPostForm(forms.ModelForm):
    class Meta:
        model = WantedPost
        field_classes = {"image": ReferenceImageField}
        fields = (
            "title",
            "image",
            "description",
            "category",
            "budget",
            "location",
        )
        labels = {
            "title": "Item you are looking for",
            "image": "Reference picture",
            "description": "What do you need?",
            "category": "Category",
            "budget": "Maximum budget",
            "location": "Your location",
        }
        help_texts = {
            "image": "This picture is for reference only. JPG, JPEG, PNG, or WEBP; maximum 5 MB and 4096 × 4096 pixels.",
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
            "image": forms.FileInput(attrs={
                "accept": ".jpg,.jpeg,.png,.webp",
                "data-reference-image": "",
            }),
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
