from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Transaction


class MobileTransactionsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = Transaction.objects.filter(
            Q(buyer=request.user) | Q(review_items__seller=request.user)
        ).distinct().order_by("-created_at")
        return Response([
            {
                "id": item.pk,
                "order_id": item.order_id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "total_amount": str(item.total_amount),
                "payment_method": item.payment_method,
                "payment_status": item.payment_status,
                "transaction_status": item.transaction_status,
            }
            for item in transactions
        ])
