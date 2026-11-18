"""Public Wanted data shared with the mobile client."""

from rest_framework import serializers

from .models import WantedPost


class WantedPostSerializer(serializers.ModelSerializer):
    requester_username = serializers.ReadOnlyField(source="requester.username")

    class Meta:
        model = WantedPost
        fields = (
            "id", "title", "description", "category", "budget", "location",
            "requester", "requester_username", "status", "created_at", "updated_at",
        )
        read_only_fields = fields
