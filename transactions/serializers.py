from rest_framework import serializers
from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "order_id",
            "buyer",
            "seller",
            "item_name",
            "quantity",
            "total_amount",
            "payment_method",
            "payment_status",
            "transaction_status",
            "shipping_address",
            "cod_meeting_location",
            "cod_meeting_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "buyer",
            "payment_status",
            "transaction_status",
            "created_at",
            "updated_at",
        ]