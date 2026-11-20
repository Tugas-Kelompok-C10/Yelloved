"""Public Wanted data shared with the mobile client."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.html import strip_tags
from rest_framework import serializers

from .creation import creation_uid
from .models import WantedPost
from .rate_limits import create_with_quota


class WantedPostSerializer(serializers.ModelSerializer):
    requester_username = serializers.ReadOnlyField(source="requester.username")
    budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    creation_token = serializers.CharField(write_only=True, required=False)
    revision = serializers.DateTimeField(write_only=True, required=False)

    class Meta:
        model = WantedPost
        fields = (
            "id", "title", "description", "category", "budget", "location",
            "requester", "requester_username", "status", "created_at", "updated_at",
            "creation_token", "revision",
        )
        read_only_fields = (
            "id", "requester", "requester_username", "status", "created_at", "updated_at",
        )

    def validate_title(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Please enter an item title.")
        return value

    def validate_description(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Please describe the item you need.")
        return value

    def validate_location(self, value):
        return strip_tags(value).strip()

    def validate_creation_token(self, value):
        try:
            return creation_uid(value, self.context["request"].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    def validate(self, attrs):
        if self.instance is None and "creation_token" not in attrs:
            raise serializers.ValidationError({"creation_token": "Get a token from create-options first."})
        if self.instance is not None and "revision" not in attrs:
            raise serializers.ValidationError({"revision": "Send the updated_at value from the latest detail."})
        return attrs

    def create(self, validated_data):
        uid = validated_data.pop("creation_token")
        validated_data.pop("revision", None)
        return create_with_quota(self.context["request"].user, uid, validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("creation_token", None)
        validated_data.pop("revision", None)
        return super().update(instance, validated_data)


class WantedStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WantedPost.Status.choices)
    revision = serializers.DateTimeField()
