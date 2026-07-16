"""DRF exception handler."""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "ok": False,
            "error": response.data,
            "status_code": response.status_code,
        }
        return response
    return Response(
        {"ok": False, "error": str(exc), "status_code": 500},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
