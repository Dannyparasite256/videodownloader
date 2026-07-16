"""Downloads URL routes."""
from django.urls import path

from . import views

app_name = "downloads"

urlpatterns = [
    path("", views.home, name="home"),
    path("metadata/", views.fetch_metadata, name="metadata"),
    path("start/", views.start_download, name="start"),
    path("bulk/", views.bulk_download, name="bulk"),
    path("history/", views.history, name="history"),
    path("files/", views.file_manager, name="files"),
    path("history/<uuid:job_id>/", views.detail, name="detail"),
    path("history/<uuid:job_id>/pause/", views.pause_download, name="pause"),
    path("history/<uuid:job_id>/resume/", views.resume_download, name="resume"),
    path("history/<uuid:job_id>/cancel/", views.cancel_download, name="cancel"),
    path("history/<uuid:job_id>/retry/", views.retry_download, name="retry"),
    path("history/<uuid:job_id>/redownload/", views.redownload, name="redownload"),
    path("history/<uuid:job_id>/delete/", views.delete_download, name="delete"),
    path("history/<uuid:job_id>/favorite/", views.toggle_favorite, name="favorite"),
    path("history/<uuid:job_id>/file/", views.download_file, name="file"),
    path("history/<uuid:job_id>/progress/", views.progress_json, name="progress"),
    path("history/<uuid:job_id>/qr/", views.qr_code, name="qr"),
]
