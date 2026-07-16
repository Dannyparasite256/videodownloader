"""WebSocket consumers for live download progress."""
from __future__ import annotations

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.downloader.progress import download_group_name, user_group_name

logger = logging.getLogger(__name__)


class DownloadProgressConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe to a single download job's progress stream."""

    async def connect(self) -> None:
        self.download_id = self.scope["url_route"]["kwargs"]["download_id"]
        self.group = download_group_name(self.download_id)

        allowed = await self._user_can_access(self.download_id)
        if not allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Send current state immediately
        snapshot = await self._get_snapshot(self.download_id)
        if snapshot:
            await self.send_json({"type": "snapshot", "data": snapshot})

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def download_progress(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "progress", "data": event["data"]})

    @database_sync_to_async
    def _user_can_access(self, download_id: str) -> bool:
        from apps.downloads.models import DownloadJob

        try:
            job = DownloadJob.objects.get(id=download_id)
        except DownloadJob.DoesNotExist:
            return False
        user = self.scope.get("user")
        if user and user.is_authenticated:
            return job.user_id == user.id or user.is_staff
        # Guests: allow if job has no user (session-bound jobs still open over WS;
        # tighten with session in production if needed)
        return job.user_id is None

    @database_sync_to_async
    def _get_snapshot(self, download_id: str) -> dict | None:
        from apps.downloads.models import DownloadJob

        try:
            job = DownloadJob.objects.get(id=download_id)
            return job.to_progress_dict()
        except DownloadJob.DoesNotExist:
            return None


class UserEventsConsumer(AsyncJsonWebsocketConsumer):
    """User-level notifications channel (queue finished, etc.)."""

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group = user_group_name(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def user_event(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {"type": event.get("event", "event"), "data": event.get("data", {})}
        )
