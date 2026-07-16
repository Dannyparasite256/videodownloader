"""REST API viewsets and endpoints."""
from __future__ import annotations

from django.http import FileResponse
from pathlib import Path

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.api.permissions import IsNotBlocked, IsOwnerOrStaff
from apps.api.serializers import (
    BulkDownloadSerializer,
    DownloadCreateSerializer,
    DownloadJobSerializer,
    FolderSerializer,
    MetadataRequestSerializer,
    TagSerializer,
)
from apps.api.throttles import (
    AnonDownloadRateThrottle,
    DownloadRateThrottle,
    MetadataRateThrottle,
)
from apps.downloads.models import DownloadJob, Folder, Tag
from repositories.download_repository import DownloadRepository
from services.download_service import DownloadService, DownloadServiceError


class MetadataView(APIView):
    """POST /api/v1/metadata/ – extract video metadata."""

    permission_classes = [AllowAny, IsNotBlocked]
    throttle_classes = [MetadataRateThrottle, AnonDownloadRateThrottle]

    def post(self, request):
        ser = MetadataRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            data = DownloadService().fetch_metadata(ser.validated_data["url"])
            return Response({"ok": True, "data": data})
        except DownloadServiceError as exc:
            return Response(
                {"ok": False, "error": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DownloadViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Download job CRUD + lifecycle actions."""

    serializer_class = DownloadJobSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsNotBlocked]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "platform", "mode", "is_favorite"]
    search_fields = ["title", "uploader", "url", "platform"]
    ordering_fields = ["created_at", "title", "file_size", "status"]
    ordering = ["-created_at"]
    lookup_field = "id"

    def get_queryset(self):
        repo = DownloadRepository()
        user = self.request.user
        session_key = ""
        if not user.is_authenticated:
            if not self.request.session.session_key:
                self.request.session.create()
            session_key = self.request.session.session_key or ""
        return repo.get_for_user(user, session_key=session_key)

    def get_permissions(self):
        if self.action in ("create", "bulk"):
            return [AllowAny(), IsNotBlocked()]
        if self.action in ("pause", "resume", "cancel", "retry", "destroy", "favorite"):
            return [AllowAny(), IsNotBlocked()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action in ("create", "bulk"):
            return [DownloadRateThrottle(), AnonDownloadRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        ser = DownloadCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        session_key = ""
        if not request.user.is_authenticated:
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key or ""
        try:
            job = DownloadService().create_download(
                data["url"],
                user=request.user,
                session_key=session_key,
                mode=data.get("mode"),
                quality=data.get("quality", "best"),
                audio_quality=data.get("audio_quality", "192"),
                output_format=data.get("output_format", "mp4"),
                audio_format=data.get("audio_format", "mp3"),
                selected_format_id=data.get("format_id") or "",
                subtitle_langs=data.get("subtitle_langs") or [],
                embed_subs=data.get("embed_subs", False),
                embed_thumbnail=data.get("embed_thumbnail", True),
                write_description=data.get("write_description", False),
                write_thumbnail=data.get("write_thumbnail", False),
                playlist_start=data.get("playlist_start"),
                playlist_end=data.get("playlist_end"),
                priority=data.get("priority", 5),
                folder_id=str(data["folder_id"]) if data.get("folder_id") else None,
                check_duplicate=data.get("check_duplicate", True),
            )
        except DownloadServiceError as exc:
            return Response(
                {"ok": False, "error": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"ok": True, "data": DownloadJobSerializer(job).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        ser = BulkDownloadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session_key = ""
        if not request.user.is_authenticated:
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key or ""
        jobs = DownloadService().create_bulk(
            ser.validated_data["urls"],
            user=request.user,
            session_key=session_key,
            mode=ser.validated_data.get("mode"),
            quality=ser.validated_data.get("quality", "best"),
            check_duplicate=False,
        )
        return Response(
            {
                "ok": True,
                "count": len(jobs),
                "data": DownloadJobSerializer(jobs, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def pause(self, request, id=None):
        return self._lifecycle(request, "pause")

    @action(detail=True, methods=["post"])
    def resume(self, request, id=None):
        return self._lifecycle(request, "resume")

    @action(detail=True, methods=["post"])
    def cancel(self, request, id=None):
        return self._lifecycle(request, "cancel")

    @action(detail=True, methods=["post"])
    def retry(self, request, id=None):
        return self._lifecycle(request, "retry")

    @action(detail=True, methods=["post"])
    def favorite(self, request, id=None):
        job = self.get_object()
        job.is_favorite = not job.is_favorite
        job.save(update_fields=["is_favorite", "updated_at"])
        return Response({"ok": True, "is_favorite": job.is_favorite})

    @action(detail=True, methods=["get"])
    def progress(self, request, id=None):
        job = self.get_object()
        return Response({"ok": True, "data": job.to_progress_dict()})

    @action(detail=True, methods=["get"])
    def file(self, request, id=None):
        job = self.get_object()
        if job.status != DownloadJob.Status.COMPLETED or not job.file_path:
            return Response(
                {"ok": False, "error": "File not ready"},
                status=status.HTTP_404_NOT_FOUND,
            )
        path = Path(job.file_path)
        if not path.exists():
            return Response(
                {"ok": False, "error": "File missing"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        DownloadRepository().soft_delete(job)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _lifecycle(self, request, action_name: str):
        job = self.get_object()
        service = DownloadService()
        try:
            fn = getattr(service, action_name)
            job = fn(job)
        except DownloadServiceError as exc:
            return Response(
                {"ok": False, "error": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"ok": True, "data": DownloadJobSerializer(job).data})


class StatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = DownloadRepository().stats_for_user(request.user)
        return Response({"ok": True, "data": stats})


class QueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DownloadJob.objects.filter(
            user=request.user,
            status__in=[
                DownloadJob.Status.QUEUED,
                DownloadJob.Status.DOWNLOADING,
                DownloadJob.Status.PROCESSING,
                DownloadJob.Status.MERGING,
                DownloadJob.Status.CONVERTING,
            ],
            is_deleted=False,
        ).order_by("-priority", "created_at")
        return Response(
            {"ok": True, "data": DownloadJobSerializer(qs, many=True).data}
        )


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Folder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness/readiness probe."""
    return Response({"ok": True, "status": "healthy", "service": "videodl-pro"})
