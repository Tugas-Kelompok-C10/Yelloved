"""Item matching data shared with the mobile client."""

from rest_framework import serializers

from .contacts import contact_for
from .models import ItemOffer, ItemRequest


class _ContactMixin:
    """Contact details are revealed only to the two parties of an accepted match."""

    def _counterpart(self, obj, user):
        raise NotImplementedError

    def get_contact(self, obj):
        request = self.context.get("request")
        if obj.status != "accepted" or request is None or not request.user.is_authenticated:
            return None
        other = self._counterpart(obj, request.user)
        return contact_for(other) if other else None


class ItemRequestSerializer(_ContactMixin, serializers.ModelSerializer):
    item_title = serializers.ReadOnlyField(source="item.title")
    owner_username = serializers.ReadOnlyField(source="item.owner.username")
    requester_username = serializers.ReadOnlyField(source="requester.username")
    contact = serializers.SerializerMethodField()

    class Meta:
        model = ItemRequest
        fields = (
            "id", "item", "item_title", "owner_username", "requester", "requester_username",
            "offered_item", "offer_price", "message", "status", "contact",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def _counterpart(self, obj, user):
        return obj.requester if obj.item.owner_id == user.pk else obj.item.owner


class ItemOfferSerializer(_ContactMixin, serializers.ModelSerializer):
    # An offer is either one of the offerer's items or a photo offer (item is null).
    title = serializers.CharField(source="display_title", read_only=True)
    image_url = serializers.CharField(source="display_image_url", read_only=True)
    price_display = serializers.CharField(read_only=True)
    wanted_title = serializers.ReadOnlyField(source="wanted_post.title")
    offerer_username = serializers.ReadOnlyField(source="offerer.username")
    contact = serializers.SerializerMethodField()

    class Meta:
        model = ItemOffer
        fields = (
            "id", "wanted_post", "wanted_title", "item", "title", "image_url", "offered_price",
            "price_display", "offerer", "offerer_username", "message", "status", "contact",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def _counterpart(self, obj, user):
        return obj.offerer if obj.wanted_post.requester_id == user.pk else obj.wanted_post.requester


class MatchSerializer(serializers.Serializer):
    """A suggested pairing from matching.evaluate()."""

    score = serializers.IntegerField(read_only=True)
    reasons = serializers.ListField(child=serializers.CharField(), read_only=True)
    item_id = serializers.IntegerField(source="item.pk", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)
    item_price_display = serializers.CharField(source="item.price_display", read_only=True)
    wanted_id = serializers.UUIDField(source="wanted_post.pk", read_only=True)
    wanted_title = serializers.CharField(source="wanted_post.title", read_only=True)
    wanted_budget = serializers.DecimalField(
        source="wanted_post.budget", max_digits=12, decimal_places=2, read_only=True,
    )
