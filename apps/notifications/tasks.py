from celery import shared_task


@shared_task(name="apps.notifications.tasks.send_pending_emails")
def send_pending_emails() -> int:
    """Placeholder for email digest delivery."""
    return 0
