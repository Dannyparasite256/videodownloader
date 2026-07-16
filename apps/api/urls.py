"""API v1 URL configuration."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("downloads", views.DownloadViewSet, basename="api-downloads")
router.register("folders", views.FolderViewSet, basename="api-folders")
router.register("tags", views.TagViewSet, basename="api-tags")

urlpatterns = [
    path("health/", views.health, name="api-health"),
    path("metadata/", views.MetadataView.as_view(), name="api-metadata"),
    path("stats/", views.StatsView.as_view(), name="api-stats"),
    path("queue/", views.QueueView.as_view(), name="api-queue"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]
