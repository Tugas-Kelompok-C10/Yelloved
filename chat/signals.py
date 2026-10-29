import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Message


def remove_attachment(name):
    try:
        Message._meta.get_field("attachment").storage.delete(name)
    except OSError:
        logging.getLogger(__name__).exception("Unable to remove private chat attachment")


@receiver(post_delete, sender=Message)
def cleanup_attachment(sender, instance, **kwargs):
    if instance.attachment:
        transaction.on_commit(lambda: remove_attachment(instance.attachment.name))
