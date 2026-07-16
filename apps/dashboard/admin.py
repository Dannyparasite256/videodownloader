"""Custom Django admin dashboard branding and helpers."""
from __future__ import annotations

from django.contrib.admin import AdminSite


def customize_admin(site: AdminSite) -> None:
    site.site_header = "VideoDL Pro Administration"
    site.site_title = "VideoDL Pro Admin"
    site.index_title = "System Control Center"
