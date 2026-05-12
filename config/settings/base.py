import environ
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env", overwrite=True)

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "config.apps.DailyLogAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.logs",
    "apps.notifications",
    "apps.audit",
    "apps.reports",
    "apps.inventory",
    "apps.schedules",
    "apps.platform",
    "apps.sigtools",
    "apps.installations",
    "apps.sigtools_auth",
    "apps.chatbot",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.daily_user.DailyUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# Authentication Backends
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "apps.users.backends.DailyUserBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
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
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — MySQL existente
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", default="sig_dailylogs"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="127.0.0.1"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
    "inventory": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("INVENTORY_DB_NAME", default="inventory"),
        "USER": env("INVENTORY_DB_USER", default="app_user"),
        "PASSWORD": env("INVENTORY_DB_PASSWORD", default=""),
        "HOST": env("INVENTORY_DB_HOST", default="192.168.101.135"),
        "PORT": env("INVENTORY_DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "latin1",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
    "schedules": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("SCHEDULES_DB_NAME", default="slc_schedules"),
        "USER": env("SCHEDULES_DB_USER", default="app_user"),
        "PASSWORD": env("SCHEDULES_DB_PASSWORD", default=""),
        "HOST": env("SCHEDULES_DB_HOST", default="192.168.101.135"),
        "PORT": env("SCHEDULES_DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
    "sigtools": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("SIGTOOLS_DB_NAME", default="sigtools_beta"),
        "USER": env("SIGTOOLS_DB_USER"),
        "PASSWORD": env("SIGTOOLS_DB_PASSWORD"),
        "HOST": env("SIGTOOLS_DB_HOST", default="72.167.56.142"),
        "PORT": env("SIGTOOLS_DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
}

DATABASE_ROUTERS = [
    "config.db_router.SchedulesRouter",
    "config.db_router.InventoryRouter",
    "config.db_router.SigtoolsRouter",
]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
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

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Default PK
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.sigtools_auth.authentication.SigtoolsCookieAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DATETIME_FORMAT": "iso-8601",
    "DATE_FORMAT": "%Y-%m-%d",
}

# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://localhost:5173",
        "https://localhost:5173",
        "http://localhost:5174",
        "https://localhost:5174",
    ],
)
CORS_ALLOW_CREDENTIALS = True

# Permite cualquier origen en la subred 192.168.101.x (red local de desarrollo)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://192\.168\.101\.\d+:\d+$",
    r"^https?://localhost:\d+$",
]

# ---------------------------------------------------------------------------
# Teams webhook (damaged article alert)
# ---------------------------------------------------------------------------
TEAMS_WEBHOOK_URL = env("TEAMS_WEBHOOK_URL", default="")

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Daily Log API",
    "DESCRIPTION": "REST API for Daily Log System - SIG Systems, Inc.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]",
}

# ---------------------------------------------------------------------------
# Sigtools Web Cookie Auth
# ---------------------------------------------------------------------------
# Cookie settings
SIGTOOLS_COOKIE_NAME = env("SIGTOOLS_COOKIE_NAME", default="sig_token")
SIGTOOLS_COOKIE_HTTPONLY = True
SIGTOOLS_COOKIE_SECURE = env.bool("SIGTOOLS_COOKIE_SECURE", default=False)
SIGTOOLS_COOKIE_SAMESITE = env("SIGTOOLS_COOKIE_SAMESITE", default="Lax")
SIGTOOLS_COOKIE_MAX_AGE = env.int("SIGTOOLS_COOKIE_MAX_AGE", default=60 * 60 * 8)  # 8 h
SIGTOOLS_COOKIE_DOMAIN = env("SIGTOOLS_COOKIE_DOMAIN", default=None)
SIGTOOLS_TOKEN_EXPIRY_MINUTES = env.int("SIGTOOLS_TOKEN_EXPIRY_MINUTES", default=480)

# LDAP / Active Directory settings
LDAP_HOST = env("LDAP_HOST", default="sig")
LDAP_DOMAIN = env("LDAP_DOMAIN", default="sig.com")
LDAP_BASE_DN = env("LDAP_BASE_DN", default="OU=OU User,DC=sig,DC=com")
