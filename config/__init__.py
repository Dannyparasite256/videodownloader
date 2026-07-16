"""Django project configuration package.

Celery app is imported so shared_task uses this app.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
