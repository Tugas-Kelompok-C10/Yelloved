"""Keep requests/offers consistent when other apps change items or wanted posts."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from items.models import Item
from wanted_board.models import WantedPost

from . import services


@receiver(post_save, sender=Item, dispatch_uid='item_matching_item_saved')
def item_saved(sender, instance, created, **kwargs):
    # e.g. the owner edits the item to Sold/Unavailable in the items app.
    if not created and instance.status != Item.Status.AVAILABLE:
        services.release_item(instance)


@receiver(post_save, sender=WantedPost, dispatch_uid='item_matching_wanted_saved')
def wanted_post_saved(sender, instance, created, **kwargs):
    # e.g. the requester marks the post fulfilled/closed from the wanted board.
    if not created and instance.status != WantedPost.Status.OPEN:
        services.close_offers_for(instance)
