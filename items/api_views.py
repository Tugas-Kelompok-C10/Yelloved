from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer

from .forms import ItemFilterForm
from .models import Item
from .serializers import ItemSerializer


class ItemListView(ListAPIView):
    serializer_class = ItemSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    def get_queryset(self):
        choice_filters = ('category', 'condition', 'listing_type')
        params = self.request.query_params
        form = ItemFilterForm({name: params.get(name, '') for name in ('q', *choice_filters)})
        if not form.is_valid():
            raise ValidationError(form.errors)

        data = form.cleaned_data
        queryset = Item.objects.filter(status=Item.Status.AVAILABLE).prefetch_related('images')
        if data['q']:
            queryset = queryset.filter(Q(title__icontains=data['q']) | Q(description__icontains=data['q']))
        return queryset.filter(**{name: data[name] for name in choice_filters if data[name]})
