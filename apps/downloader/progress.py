"""WebSocket progress broadcasting for download jobs."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def download_group_name(download_id: str | UUID) -> str:
    return f"download_{download_id}"


def user_group_name(user_id: str | UUID) -> str:
    return f"user_{user_id}"


def broadcast_progress(download_id: str | UUID, payload: dict[str, Any]) -> None:
    """Push progress event to the download-specific WebSocket group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            download_group_name(download_id),
            {"type": "download.progress", "data": payload},
        )
    except Exception:
        logger.exception("Failed to broadcast progress for %s", download_id)


def broadcast_user_event(user_id: str | UUID, event: str, payload: dict[str, Any]) -> None:
    """Push a notification-style event to a user's channel group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            user_group_name(user_id),
            {"type": "user.event", "event": event, "data": payload},
        )
    except Exception:
        logger.exception("Failed to broadcast user event for %s", user_id)
