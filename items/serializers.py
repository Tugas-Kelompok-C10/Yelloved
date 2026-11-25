from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    price_display = serializers.CharField(read_only=True)
    image_url = serializers.CharField(source='display_image_url', read_only=True)
    detail_url = serializers.CharField(source='get_absolute_url', read_only=True)

    class Meta:
        model = Item
        fields = (
            'id', 'title', 'description', 'category', 'condition', 'listing_type',
            'price_display', 'location', 'image_url', 'status', 'detail_url',
        )
        read_only_fields = fields
