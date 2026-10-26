from django.contrib import admin

from .models import ItemOffer, ItemRequest


@admin.register(ItemRequest)
class ItemRequestAdmin(admin.ModelAdmin):
    list_display = ('item', 'requester', 'offered_item', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('item__title', 'requester__username')
    raw_id_fields = ('item', 'offered_item', 'requester')


@admin.register(ItemOffer)
class ItemOfferAdmin(admin.ModelAdmin):
    list_display = ('item', 'wanted_post', 'offerer', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('item__title', 'wanted_post__title', 'offerer__username')
    raw_id_fields = ('item', 'wanted_post', 'offerer')
