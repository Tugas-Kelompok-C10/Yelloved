from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import WantedCreationReceipt, WantedPost


@receiver(post_save, sender=WantedPost)
def remember_created_post(sender, instance, created, using, **kwargs):
    if created:
        WantedCreationReceipt.objects.using(using).get_or_create(
            pk=instance.pk, defaults={"requester_id": instance.requester_id})


@receiver(pre_delete, sender=WantedPost)
def remember_deleted_post(sender, instance, using, **kwargs):
    # Covers owner deletes, admin deletes, and QuerySet/cascade deletes too.
    WantedCreationReceipt.objects.using(using).filter(pk=instance.pk).update(deleted_at=timezone.now())
