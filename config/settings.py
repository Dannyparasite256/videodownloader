"""
Django settings for VideoDL Pro – industrial-grade video downloader.

Uses django-environ for 12-factor configuration. Secure defaults for production;
override via environment variables / .env file.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    MAX_CONCURRENT_DOWNLOADS=(int, 5),
    MAX_DOWNLOAD_SIZE_MB=(int, 2048),
    DEFAULT_BANDWIDTH_LIMIT_KBPS=(int, 0),
    YTDLP_SOCKET_TIMEOUT=(int, 30),
    YTDLP_RETRIES=(int, 3),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-in-production-xyz123")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:8000", "http://127.0.0.1:8000"],
)

# ---------------------------------------------------------------------------
# Multi-device access (phones, tablets, other PCs, public tunnel)
# ---------------------------------------------------------------------------
# When True (default for home hosting): accept any Host header so LAN IPs and
# Cloudflare / trycloudflare hostnames work without editing .env every time.
ALLOW_MULTI_DEVICE = env.bool("ALLOW_MULTI_DEVICE", default=True)
if ALLOW_MULTI_DEVICE:
    ALLOWED_HOSTS = ["*"]

SITE_NAME = env("SITE_NAME", default="VideoDL Pro")
SITE_URL = env("SITE_URL", default="http://localhost:8000")
SITE_ID = 1

# ---------------------------------------------------------------------------
# Render.com (and similar PaaS) auto-config
# ---------------------------------------------------------------------------
# Render sets RENDER=true and RENDER_EXTERNAL_HOSTNAME for web services.
IS_RENDER = env.bool("RENDER", default=False) or bool(
    os.environ.get("RENDER_EXTERNAL_HOSTNAME") or os.environ.get("RENDER_SERVICE_ID")
)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
if not RENDER_EXTERNAL_URL and RENDER_EXTERNAL_HOSTNAME:
    RENDER_EXTERNAL_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}"

if IS_RENDER:
    # Hosts
    if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    if ".onrender.com" not in ALLOWED_HOSTS and "*.onrender.com" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".onrender.com")
    # CSRF / site URL
    if RENDER_EXTERNAL_URL:
        if RENDER_EXTERNAL_URL not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(RENDER_EXTERNAL_URL)
        SITE_URL = env("SITE_URL", default=RENDER_EXTERNAL_URL)
# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "django_celery_beat",
    "django_celery_results",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "axes",
    # Local apps
    "apps.accounts",
    "apps.downloads",
    "apps.downloader",
    "apps.api",
    "apps.dashboard",
    "apps.notifications",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "middleware.multi_device.MultiDeviceCSRFMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
    "middleware.audit.AuditLogMiddleware",
    "middleware.security_headers.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "utils.context_processors.site_settings",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Prefer DATABASE_URL (Render/Heroku). Fall back to SQLite for local dev / free tier.
_db_url = env("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
if _db_url.startswith("postgres://"):
    _db_url = "postgresql://" + _db_url[len("postgres://") :]

# Free Render often keeps a broken Postgres URL after a failed Blueprint.
# Allow forcing SQLite without editing every linked env var.
if env.bool("FORCE_SQLITE", default=False) or (
    IS_RENDER and env.bool("RENDER_USE_SQLITE", default=False)
):
    _db_path = (BASE_DIR / "db.sqlite3").as_posix()
    _db_url = f"sqlite:///{_db_path}"

DATABASES = {"default": environ.Env.db_url_config(_db_url)}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"]["OPTIONS"] = {"timeout": 20}
else:
    DATABASES["default"]["CONN_MAX_AGE"] = 60
    DATABASES["default"]["ATOMIC_REQUESTS"] = False
    # Render Postgres requires SSL
    if IS_RENDER:
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"].setdefault("sslmode", "require")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "downloads:home"
LOGOUT_REDIRECT_URL = "downloads:home"

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SESSION_REMEMBER = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
        },
    },
    "github": {
        "SCOPE": ["user:email"],
        "APP": {
            "client_id": env("GITHUB_CLIENT_ID", default=""),
            "secret": env("GITHUB_CLIENT_SECRET", default=""),
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("ja", "日本語"),
    ("zh-hans", "简体中文"),
    ("ar", "العربية"),
    ("pt", "Português"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Production: hashed+compressed assets, but never 500 if a file is missing from the
# collectstatic manifest (common after adding static/*.js without redeploying cleanly).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "utils.storage.ForgivingManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
# WhiteNoise: same lenient behaviour when serving from the manifest
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
DOWNLOAD_ROOT = Path(env("DOWNLOAD_ROOT", default=str(MEDIA_ROOT / "downloads")))

# Render persistent disk (mount at /var/data) — survives deploys
if IS_RENDER and Path("/var/data").is_dir():
    MEDIA_ROOT = Path(env("MEDIA_ROOT", default="/var/data/media"))
    DOWNLOAD_ROOT = Path(env("DOWNLOAD_ROOT", default="/var/data/downloads"))
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Cache / Redis
# ---------------------------------------------------------------------------
# On Render, one Redis URL is used for cache, Celery, and Channels unless overridden.
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

def _redis_is_reachable(url: str, timeout: float = 1.5) -> bool:
    try:
        import redis as _redis_lib

        _client = _redis_lib.from_url(url, socket_connect_timeout=timeout)
        _client.ping()
        return True
    except Exception:
        return False


_redis_ok = _redis_is_reachable(REDIS_URL)

if _redis_ok:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "IGNORE_EXCEPTIONS": True,
            },
            "KEY_PREFIX": "vdl",
        }
    }
else:
    # Free Render / offline Redis: keep the web process up
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "vdl-local",
        }
    }

# ---------------------------------------------------------------------------
# Channels (WebSockets)
# ---------------------------------------------------------------------------
CHANNELS_REDIS_URL = env("CHANNELS_REDIS_URL", default=REDIS_URL)
if _redis_ok or _redis_is_reachable(CHANNELS_REDIS_URL):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CHANNELS_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
# Default Celery to the same Redis as REDIS_URL (Render provides one Redis)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 60 * 4  # 4 hours
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 60 * 3
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Run tasks inline when Redis/broker is unavailable (local + free Render)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
if not CELERY_TASK_ALWAYS_EAGER and not _redis_is_reachable(CELERY_BROKER_URL):
    CELERY_TASK_ALWAYS_EAGER = True

# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "1000/hour",
        "download": "30/hour",
        "metadata": "120/hour",
    },
    "EXCEPTION_HANDLER": "apps.api.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "VideoDL Pro API",
    "DESCRIPTION": "Industrial-grade video download REST API powered by yt-dlp",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# Download Engine
# ---------------------------------------------------------------------------
MAX_CONCURRENT_DOWNLOADS = env("MAX_CONCURRENT_DOWNLOADS")
MAX_DOWNLOAD_SIZE_MB = env("MAX_DOWNLOAD_SIZE_MB")
DEFAULT_BANDWIDTH_LIMIT_KBPS = env("DEFAULT_BANDWIDTH_LIMIT_KBPS")
YTDLP_SOCKET_TIMEOUT = env("YTDLP_SOCKET_TIMEOUT")
YTDLP_RETRIES = env("YTDLP_RETRIES")
DOWNLOAD_EXPIRY_DAYS = env.int("DOWNLOAD_EXPIRY_DAYS", default=7)
GUEST_MAX_DOWNLOADS_PER_DAY = env.int("GUEST_MAX_DOWNLOADS_PER_DAY", default=5)
USER_STORAGE_QUOTA_MB = env.int("USER_STORAGE_QUOTA_MB", default=5120)

# YouTube often requires browser cookies on cloud IPs ("Sign in to confirm you're not a bot").
# Priority: YTDLP_COOKIES_FILE → secrets/cookies.txt → YTDLP_COOKIES_BASE64 → browser.
# See docs/YOUTUBE_COOKIES.md
YTDLP_COOKIES_FILE = env("YTDLP_COOKIES_FILE", default="")
YTDLP_COOKIES_FROM_BROWSER = env("YTDLP_COOKIES_FROM_BROWSER", default="")
YTDLP_COOKIES_BASE64 = env("YTDLP_COOKIES_BASE64", default="")
YTDLP_USER_AGENT = env(
    "YTDLP_USER_AGENT",
    default=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
)

# Auto-detect project secrets/cookies.txt if no path set
if not YTDLP_COOKIES_FILE:
    for candidate in (
        BASE_DIR / "secrets" / "cookies.txt",
        BASE_DIR / "cookies.txt",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            YTDLP_COOKIES_FILE = str(candidate)
            break

if YTDLP_COOKIES_BASE64 and not YTDLP_COOKIES_FILE:
    import base64
    import tempfile

    try:
        raw = base64.b64decode(YTDLP_COOKIES_BASE64)
        # Accept URL-safe base64 and whitespace
        if not raw:
            raw = base64.urlsafe_b64decode(YTDLP_COOKIES_BASE64 + "==")
        secrets_dir = BASE_DIR / "secrets"
        secrets_dir.mkdir(exist_ok=True)
        cookie_path = secrets_dir / "cookies.from_env.txt"
        cookie_path.write_bytes(raw)
        try:
            os.chmod(cookie_path, 0o600)
        except OSError:
            pass
        YTDLP_COOKIES_FILE = str(cookie_path)
    except Exception:
        YTDLP_COOKIES_FILE = ""

# Do NOT auto-enable cookies-from-browser: on modern Chrome (Windows) it often
# fails with DPAPI / app-bound encryption and breaks extraction entirely.
# Prefer secrets/cookies.txt or YTDLP_COOKIES_BASE64 (see docs/YOUTUBE_COOKIES.md).

# Legal notice – respect ToS and copyright
DOWNLOAD_DISCLAIMER = (
    "Only download content you have the right to download. "
    "Respect platform Terms of Service and copyright law. "
    "This tool does not bypass DRM or access controls."
)

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# Defaults flip to secure cookies / SSL redirect when hosted on Render
_secure_default = IS_RENDER and not DEBUG
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=_secure_default)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=_secure_default)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=_secure_default)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if IS_RENDER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cloudflare Tunnel / reverse proxies terminate TLS and forward HTTP locally
if ALLOW_MULTI_DEVICE or env.bool("BEHIND_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:4000", "http://127.0.0.1:4000"],
)
CORS_ALLOW_CREDENTIALS = True
# Home multi-device / tunnel: allow API clients from any device origin
if ALLOW_MULTI_DEVICE:
    CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@videodl.local")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {module}:{lineno} | {message}",
            "style": "{",
        },
        "json": {
            "()": "utils.logging.JSONFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "json",
        },
        "download_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "downloads.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "apps.downloader": {
            "handlers": ["console", "download_file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "apps.downloads": {
            "handlers": ["console", "download_file"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
