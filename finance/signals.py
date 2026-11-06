from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import DEFAULT_CATEGORIES
from .models import Category


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_categories(sender, instance, created, **kwargs):
    if not created:
        return
    Category.objects.bulk_create(
        [
            Category(user=instance, name=name, type=type_, color=color, icon=icon)
            for name, type_, color, icon in DEFAULT_CATEGORIES
        ]
    )
