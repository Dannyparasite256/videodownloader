"""Account signals."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


@receiver(post_save, sender=User)
def user_created(sender, instance: User, created: bool, **kwargs) -> None:
    if created:
        # Future: create default folders, send welcome email, etc.
        pass
