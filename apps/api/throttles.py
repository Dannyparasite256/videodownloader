"""Custom throttle rates for sensitive endpoints."""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class DownloadRateThrottle(UserRateThrottle):
    scope = "download"


class MetadataRateThrottle(UserRateThrottle):
    scope = "metadata"


class AnonDownloadRateThrottle(AnonRateThrottle):
    scope = "download"
