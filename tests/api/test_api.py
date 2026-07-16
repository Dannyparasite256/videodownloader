"""API integration tests."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from apps.downloads.models import DownloadJob


@pytest.mark.django_db
def test_health(api_client):
    res = api_client.get("/api/v1/health/")
    assert res.status_code == 200
    assert res.json()["ok"] is True


@pytest.mark.django_db
def test_metadata_invalid_url(api_client):
    res = api_client.post("/api/v1/metadata/", {"url": "not-valid"}, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_download_invalid(api_client):
    res = api_client.post("/api/v1/downloads/", {"url": "nope"}, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_downloads_empty(auth_client):
    res = auth_client.get("/api/v1/downloads/")
    assert res.status_code == 200


@pytest.mark.django_db
def test_stats_requires_auth(api_client):
    res = api_client.get("/api/v1/stats/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_stats_authenticated(auth_client, user):
    DownloadJob.objects.create(
        user=user,
        url="https://example.com/v/1",
        title="Test",
        status=DownloadJob.Status.COMPLETED,
        platform="example",
    )
    res = auth_client.get("/api/v1/stats/")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["data"]["total"] >= 1


@pytest.mark.django_db
def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Download" in res.content or b"video" in res.content.lower()


@pytest.mark.django_db
def test_register_and_login(client):
    res = client.post(
        reverse("accounts:register"),
        {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "complex-pass-9999",
            "password2": "complex-pass-9999",
        },
    )
    assert res.status_code in (200, 302)
