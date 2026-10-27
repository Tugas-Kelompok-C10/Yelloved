import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import WantedPost


logger = logging.getLogger(__name__)


def delete_unreferenced_image(storage, name, using):
    if not name or not name.startswith("wanted_references/"):
        return

    def cleanup():
        if not WantedPost.objects.using(using).filter(image=name).exists():
            try:
                storage.delete(name)
            except OSError:
                logger.exception("Could not remove wanted reference image %s", name)

    transaction.on_commit(cleanup, using=using)


@receiver(pre_save, sender=WantedPost)
def remember_previous_image(sender, instance, using, update_fields, **kwargs):
    instance._previous_image_name = None
    if instance._state.adding or (update_fields is not None and "image" not in update_fields):
        return
    previous = sender.objects.using(using).filter(pk=instance.pk).values_list("image", flat=True).first()
    if previous and previous != instance.image.name:
        instance._previous_image_name = previous


@receiver(post_save, sender=WantedPost)
def cleanup_replaced_image(sender, instance, using, **kwargs):
    delete_unreferenced_image(
        instance.image.storage, getattr(instance, "_previous_image_name", None), using
    )


@receiver(post_delete, sender=WantedPost)
def cleanup_deleted_image(sender, instance, using, **kwargs):
    delete_unreferenced_image(instance.image.storage, instance.image.name, using)
