"""API permissions."""
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.user and request.user.is_staff:
            return True
        owner = getattr(obj, "user", None)
        return owner is not None and owner == request.user


class IsNotBlocked(BasePermission):
    message = "Account is blocked."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if user and user.is_authenticated and getattr(user, "is_blocked", False):
            return False
        return True
