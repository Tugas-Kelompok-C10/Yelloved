from django.db.models import Avg, Count
from .models import Review


def received_reviews(seller):
    return Review.objects.filter(seller=seller, transaction__transaction_status='completed').select_related('reviewer')


def review_summary(seller):
    data = received_reviews(seller).aggregate(review_score=Avg('rating'), review_count=Count('pk'))
    return data
