"""API serializers."""
from __future__ import annotations

from rest_framework import serializers

from apps.downloads.models import DownloadJob, Folder, Tag


class MetadataRequestSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)


class DownloadCreateSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)
    mode = serializers.ChoiceField(
        choices=DownloadJob.Mode.choices,
        default=DownloadJob.Mode.VIDEO_AUDIO,
    )
    quality = serializers.CharField(max_length=32, default="best")
    audio_quality = serializers.CharField(max_length=32, default="192")
    output_format = serializers.CharField(max_length=16, default="mp4")
    audio_format = serializers.CharField(max_length=16, default="mp3")
    format_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    subtitle_langs = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    embed_subs = serializers.BooleanField(default=False)
    embed_thumbnail = serializers.BooleanField(default=True)
    write_description = serializers.BooleanField(default=False)
    write_thumbnail = serializers.BooleanField(default=False)
    playlist_start = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    playlist_end = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    priority = serializers.IntegerField(default=5)
    check_duplicate = serializers.BooleanField(default=True)
    folder_id = serializers.UUIDField(required=False, allow_null=True)


class BulkDownloadSerializer(serializers.Serializer):
    urls = serializers.ListField(
        child=serializers.URLField(max_length=2048),
        min_length=1,
        max_length=50,
    )
    mode = serializers.ChoiceField(
        choices=DownloadJob.Mode.choices,
        default=DownloadJob.Mode.VIDEO_AUDIO,
    )
    quality = serializers.CharField(max_length=32, default="best")


class DownloadJobSerializer(serializers.ModelSerializer):
    progress_payload = serializers.SerializerMethodField()

    class Meta:
        model = DownloadJob
        fields = [
            "id",
            "url",
            "platform",
            "platform_display",
            "title",
            "uploader",
            "thumbnail_url",
            "duration",
            "view_count",
            "like_count",
            "mode",
            "quality",
            "audio_quality",
            "output_format",
            "status",
            "stage",
            "progress",
            "speed_bps",
            "eta_seconds",
            "downloaded_bytes",
            "total_bytes",
            "file_size",
            "resolution",
            "vcodec",
            "acodec",
            "fps",
            "is_favorite",
            "is_playlist",
            "error_message",
            "created_at",
            "completed_at",
            "expires_at",
            "progress_payload",
        ]
        read_only_fields = fields

    def get_progress_payload(self, obj: DownloadJob) -> dict:
        return obj.to_progress_dict()


class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ["id", "name", "color", "parent", "created_at"]
        read_only_fields = ["id", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        read_only_fields = ["id"]
