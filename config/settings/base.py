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
    "apps.codegen",
    "apps.layers",
    "apps.test",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Wrapper async-capable de WhiteNoise: el original es sync-only y bufferiza
    # los streams SSE (los eventos solo salían al cerrar la conexión).
    "apps.core.middleware.whitenoise_async.AsyncWhiteNoiseMiddleware",
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
        "CONN_MAX_AGE": 60,
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
        "CONN_MAX_AGE": 60,
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
        "CONN_MAX_AGE": 60,
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
        "CONN_MAX_AGE": 60,
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
    # "config.db_router.InventoryRouter",  # uncomment when inventory gets its own DB
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
# Media (user-uploaded files — e.g. indoor floor-plan maps)
# Stored on a local volume and served by nginx at /media/ in production.
# ---------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

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
        "https://installations.sig.systems",
        "https://inventory.sig.systems",
    ],
)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://localhost:5173",
        "https://localhost:5173",
        "http://localhost:5174",
        "https://localhost:5174",
        "https://installations.sig.systems",
        "https://inventory.sig.systems",
    ],
)

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
# Microsoft Graph Mail (Client Credentials)
# ---------------------------------------------------------------------------
# Accept either the MS_GRAPH_* names or the MICROSOFT_* names (fallback) so the
# same .env works regardless of which convention the environment uses.
MS_GRAPH_TENANT_ID = env("MS_GRAPH_TENANT_ID", default="") or env("MICROSOFT_TENANT_ID", default="")
MS_GRAPH_CLIENT_ID = env("MS_GRAPH_CLIENT_ID", default="") or env("MICROSOFT_CLIENT_ID", default="")
MS_GRAPH_CLIENT_SECRET = env("MS_GRAPH_CLIENT_SECRET", default="") or env("MICROSOFT_CLIENT_SECRET", default="")
MS_GRAPH_SENDER = env("MS_GRAPH_SENDER", default="") or env("MICROSOFT_SENDER", default="")

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "SIG & SLC Platform API",
    "DESCRIPTION": (
        "REST API de la Plataforma SIG & SLC — SIG Systems, Inc.\n\n"
        "---\n\n"
        "## Autenticación\n\n"
        "La API soporta **dos esquemas de autenticación** independientes:\n\n"
        "### 1 · JWT Bearer — Daily Log / Mobile / SPA\n"
        "Usado por el Daily Log y las apps de scheduling.\n\n"
        "```\n"
        "Authorization: Bearer <access_token>\n"
        "```\n\n"
        "1. Obtén el par de tokens con `POST /api/v1/auth/login/`.\n"
        "2. Incluye el `access_token` en el header `Authorization: Bearer …` de cada petición.\n"
        "3. Cuando el access token expire (60 min) renuévalo con `POST /api/v1/auth/token/refresh/` "
        "enviando el `refresh_token` (válido 7 días). Se devuelve un nuevo par y el refresh anterior "
        "queda invalidado (rotación automática).\n\n"
        "### 2 · Cookie SIGTools — Portal Web / LDAP\n"
        "Usado por el portal web `installations.sig.systems` e `inventory.sig.systems`.\n\n"
        "1. Llama a `POST /api/v1/web-auth/login/` con credenciales de Active Directory.\n"
        "2. El servidor setea la cookie `sig_token` (HttpOnly, Secure en producción, SameSite=Lax, "
        "expira en 8 h).\n"
        "3. El browser la incluye automáticamente en peticiones al mismo dominio (`*.sig.systems`).\n"
        "4. Cierra sesión con `POST /api/v1/web-auth/logout/` (revoca el token actual) o "
        "`POST /api/v1/web-auth/logout-all/` (revoca todos los tokens del usuario).\n\n"
        "---\n\n"
        "## Paginación\n\n"
        "Todos los endpoints de listado devuelven la estructura estándar:\n\n"
        "```json\n"
        '{\n  "count": 150,\n  "next": "https://api.sig.systems/api/v1/...?page=2",\n'
        '  "previous": null,\n  "results": [...]\n}\n'
        "```\n\n"
        "Tamaño de página por defecto: **50 registros**. Navega con `?page=N`.\n\n"
        "---\n\n"
        "## Streams de Tiempo Real (SSE)\n\n"
        "Dos endpoints entregan eventos SSE via Redis pub/sub:\n\n"
        "| Endpoint | Canal Redis | Descripción |\n"
        "|----------|-------------|-------------|\n"
        "| `GET /api/v1/inventory/stream/` | `rt:inventory` | Cambios en artículos de inventario |\n"
        "| `GET /api/v1/installations/stream/` | `rt:installations` | Actualizaciones de proyectos |\n\n"
        "Conéctate con `EventSource` desde JavaScript. La autenticación se pasa vía cookie o header.\n\n"
        "---\n\n"
        "## Manejo de Errores\n\n"
        "| Código | Significado |\n"
        "|--------|-------------|\n"
        "| `400` | Datos de entrada inválidos — el cuerpo incluye detalle de los campos |\n"
        "| `401` | No autenticado — token ausente o expirado |\n"
        "| `403` | Sin permiso — autenticado pero sin el rol requerido |\n"
        "| `404` | Recurso no encontrado |\n"
        "| `409` | Conflicto — violación de unicidad |\n"
        "| `500` | Error interno del servidor |"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]",
    # Servidores disponibles — el front puede seleccionar entre local y producción
    "SERVERS": [
        {"url": "http://localhost", "description": "Desarrollo local (nginx → puerto 80)"},
        {"url": "https://api.sig.systems", "description": "Producción"},
    ],
    # Tags — agrupan los endpoints en el Swagger UI
    "TAGS": [
        {
            "name": "Health",
            "description": "Health check del servidor. No requiere autenticación.",
        },
        {
            "name": "Auth",
            "description": (
                "Autenticación JWT para el Daily Log y apps móviles/SPA.\n\n"
                "Flujo típico:\n"
                "1. `POST /api/v1/auth/login/` → obtén `access` y `refresh` tokens.\n"
                "2. Incluye `Authorization: Bearer <access>` en cada request.\n"
                "3. `POST /api/v1/auth/token/refresh/` cuando el access expire.\n"
                "4. `POST /api/v1/auth/logout/` para invalidar la sesión."
            ),
        },
        {
            "name": "Web Auth",
            "description": (
                "Autenticación basada en cookie LDAP/Active Directory para el portal web.\n\n"
                "La cookie `sig_token` se setea al hacer login y se incluye automáticamente "
                "en peticiones al dominio `*.sig.systems`."
            ),
        },
        {
            "name": "Platform",
            "description": (
                "Módulo de plataforma: login por número de estación, configuración de "
                "estación y catálogo de herramientas disponibles."
            ),
        },
        {
            "name": "Catalogs",
            "description": "Catálogos de solo lectura: sitios disponibles y tipos de actividad.",
        },
        {
            "name": "Events",
            "description": (
                "Registro de eventos del Daily Log. Cada evento pertenece a un turno y un sitio.\n\n"
                "- `GET /api/v1/events/` — lista eventos del turno activo (filtrado por `site_id`, `date`).\n"
                "- `POST /api/v1/events/` — crea un nuevo evento de log."
            ),
        },
        {
            "name": "Notifications",
            "description": (
                "Especiales de supervisor (avisos que requieren confirmación).\n\n"
                "Solo accesible con el rol `Supervisor`. "
                "`PATCH /api/v1/specials/{id}/mark/` marca un especial como leído/procesado."
            ),
        },
        {
            "name": "Reports",
            "description": "Reportes de despacho policial — listado de incidentes por sitio y fecha.",
        },
        {
            "name": "Inventory",
            "description": (
                "Gestión completa del inventario físico.\n\n"
                "**Artículos:** CRUD de artículos con SKU único, categoría y estado.\n"
                "**Grupos:** Clasificación de artículos por empresa.\n"
                "**Solicitudes de materiales:** flujo solicitud → revisión.\n"
                "**Cable Runs:** registro de tendidos de cable por instalación.\n"
                "**Scope Changes:** cambios de alcance con flujo de aprobación.\n"
                "**Equipment Returns:** devoluciones con confirmación de recepción.\n"
                "**Reportes diarios:** resumen por sitio y turno.\n"
                "**Dashboard:** estadísticas agregadas."
            ),
        },
        {
            "name": "Schedules",
            "description": (
                "Módulo de programación de turnos.\n\n"
                "**Cuadrillas (Squads):** grupos de técnicos con elegibilidad configurable.\n"
                "**Tipos de turno:** catálogo de modalidades de turno.\n"
                "**Horarios:** upsert individual, bulk y borrado por rango de fechas.\n"
                "**Slots disponibles:** publicación de turnos abiertos para claims.\n"
                "**Claims:** un técnico reclama (o libera) un slot disponible.\n"
                "**Solicitudes de cancelación:** flujo para cancelar un turno asignado.\n"
                "**Notificaciones:** avisos de cambio de turno con mark-as-read."
            ),
        },
        {
            "name": "Installations",
            "description": (
                "Módulo central de gestión de proyectos de instalación.\n\n"
                "**Sitios:** listado, detalle, status, onboarding via `project_sites`.\n"
                "**Canvas de dispositivos:** posicionamiento, jerarquía, capas.\n"
                "**Flujo de despacho:** despacho → recepción → instalación por dispositivo.\n"
                "**BOM:** bill of materials por sitio.\n"
                "**Proyectos SIG:** proyectos internos con flujo de aprobación.\n"
                "**Admin:** gestión de usuarios, roles y permisos (RBAC).\n"
                "**Dashboard CEO:** métricas agregadas de alto nivel."
            ),
        },
        {
            "name": "Layers",
            "description": (
                "Catálogo de capas (layers) usadas en el canvas de instalaciones. "
                "Cada capa agrupa dispositivos en un plano independiente dentro de una instalación."
            ),
        },
        {
            "name": "SIGTools",
            "description": (
                "Proxy de solo lectura a la base de datos externa `sigtools_beta`. "
                "Expone el catálogo de sitios del sistema legacy."
            ),
        },
        {
            "name": "Chatbot",
            "description": (
                "Integración con Claude AI (Anthropic). Solo accesible para admins.\n\n"
                "- `POST /api/v1/chatbot/message/` — envía un mensaje y recibe respuesta del modelo.\n"
                "- `GET /api/v1/chatbot/ping/` — verifica que la API key de Claude esté configurada."
            ),
        },
        {
            "name": "CodeGen",
            "description": (
                "Generación de código con IA (Claude + Ollama) con auditoría. Solo admins.\n\n"
                "Flujo: generar → revisar en auditoría → aprobar o rechazar."
            ),
        },
    ],
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
        "persistAuthorization": True,
        "defaultModelsExpandDepth": 1,
        "defaultModelExpandDepth": 2,
        "docExpansion": "list",
        "tryItOutEnabled": False,
    },
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

# ---------------------------------------------------------------------------
# Redis — pub/sub y caché compartida
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
            "IGNORE_EXCEPTIONS": True,  # si Redis cae, sigue con miss de caché
        },
        "KEY_PREFIX": "dlb",
        "TIMEOUT": 300,  # 5 min default TTL
    }
}

# ---------------------------------------------------------------------------
# Logging — errors to stdout so `docker logs` captures them
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "apps.chatbot": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
