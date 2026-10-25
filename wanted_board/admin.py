from django.contrib import admin

from .models import Offer, WantedPost


class OfferInline(admin.TabularInline):
    model = Offer
    extra = 0


@admin.register(WantedPost)
class WantedPostAdmin(admin.ModelAdmin):
    list_display = ("title", "requester", "category", "status", "created_at")
    list_filter = ("status", "category", "preferred_condition")
    search_fields = ("title", "description", "requester__username")
    inlines = (OfferInline,)


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("wanted_post", "offerer", "offered_price", "created_at")
    search_fields = ("wanted_post__title", "offerer__username", "message")
