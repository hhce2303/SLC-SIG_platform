# Daily Log Backend — Agent Instructions

Django 5.1 / DRF 3.15 / Python 3.12. REST API backend for SIG Systems monitoring platform. See [README.md](README.md) for full project context and DB schema.

---

## Architecture: Selector / Service / View

Every app follows this strict separation. Use `apps/inventory/` as the canonical example.

| Layer | File | Responsibility |
|---|---|---|
| **Model** | `models.py` | Data shape only. `managed = False` for legacy MySQL tables. |
| **Selector** | `selectors.py` | Read-only queries. Always `select_related`/`prefetch_related`. Returns `QuerySet` or `dict`. Zero side effects. |
| **Service** | `services.py` | Write operations + business logic. Use `transaction.atomic()` for multi-step writes. Keyword-only `data` args (`*, data:`). |
| **View** | `views.py` | `APIView` only. Validates with serializer → calls selector or service → returns `Response`. **No business logic here.** |
| **Serializer** | `serializers.py` | Split into `ReadSerializer` (ModelSerializer) and `WriteSerializer` (plain Serializer). Expose **camelCase** to frontend via `source=` mapping. |
| **URL** | `urls.py` | Flat `path()` list. No `DefaultRouter`. No `app_name` namespace. |

**Never** call `Model.objects.*` directly in views or serializers.

---

## Databases

| Key | DB Name | Host env var | Notes |
|---|---|---|---|
| `default` | `sig_dailylogs` | `DB_HOST` | Main app DB |
| `inventory` | `inventory` | `INVENTORY_DB_HOST` | `latin1` charset — beware encoding |
| `schedules` | `slc_schedules` | `SCHEDULES_DB_HOST` | Routed by `SchedulesRouter` |
| `sigtools` | `sigtools_beta` | `SIGTOOLS_DB_HOST` | Routed by `SigtoolsRouter` |

Active routers in `DATABASE_ROUTERS`: `SchedulesRouter`, `SigtoolsRouter`. The `InventoryRouter` is **commented out** — `apps.inventory` uses `default`.

> ⚠️ Duplicate `InventoryRouter` class in [config/db_router.py](config/db_router.py). Harmless while commented out, but will `NameError` if activated without fixing.

---

## Adding a New App

1. Create the app: `python manage.py startapp <name>` under `apps/`
2. Add `"apps.<name>"` to `LOCAL_APPS` in [config/settings/base.py](config/settings/base.py)
3. Add `path("<prefix>/", include("apps.<name>.urls"))` to `api_v1` in [config/urls.py](config/urls.py)
4. If the app uses a non-default DB, add a router to [config/db_router.py](config/db_router.py) and register it in `DATABASE_ROUTERS`
5. Run `python manage.py makemigrations <name>` then `migrate`

---

## URL Pattern

All endpoints live under `/api/v1/`. Example registrations in [config/urls.py](config/urls.py):

```python
path("inventory/", include("apps.inventory.urls")),
path("chatbot/", include("apps.chatbot.urls")),
```

Four separate admin sites are mounted at `/admin/inventory/`, `/admin/schedules/`, `/admin/sigtools/`, `/admin/installations/`.

---

## Deployment (no rebuild needed for `.py` changes)

```powershell
$base = "C:\Users\hcruz.SIG\OneDrive - SIG Systems, Inc\Desktop\SLC&SIG_platform"
docker cp "$base\apps\<app>\<file>.py" daily-log-backend:/app/apps/<app>/<file>.py
docker compose -f "$base\docker\docker-compose.yml" restart web
```

Full rebuild (Dockerfile / docker-compose.yml changes):
```powershell
docker compose -f "$base\docker\docker-compose.yml" up --build -d
```

Download chatbot-written files back to local:
```powershell
.\sync_from_container.ps1
```

Container name: `daily-log-backend`. Service name: `web`. Port: `8000`.

---

## Gunicorn Workers

`gthread` worker class — 2 workers × 4 threads — timeout 180s. Do **not** change to `sync` workers (causes SIGALRM kills on long Claude API calls).

---

## Authentication

- `JWTAuthentication` (SimpleJWT) — standard API clients
- `SigtoolsCookieAuthentication` — SigTools cookie session (checked first)
- `SessionAuthentication` — Django admin session (chatbot widget)

All endpoints require `IsAuthenticated` unless explicitly overridden.

---

## Chatbot App (`apps/chatbot/`)

Stateless — no models, no migrations. Wraps Claude API in an agentic tool-use loop.

- `services.py` — `handle_message(message, history, user)`. Uses `claude-haiku-4-5` for queries, `claude-sonnet-4-6` for code-gen (keyword-detected). Max 15 tool rounds, history trimmed to last 6 turns. `max_retries=0` on the Anthropic client (prevents SDK-internal `time.sleep` that kills gunicorn workers).
- `tools.py` — 14 tools. `WRITE_TOOLS` (`write_project_file`, `restart_service`) require `is_staff`.
- `write_project_file` is restricted to `apps/` directory only.
- `restart_service` fires after a 15s delay via Docker Engine HTTP API over `/var/run/docker.sock`.

---

## Key Conventions

- **camelCase API responses** — serializers map `snake_case` model fields to `camelCase` via `source=`
- **No DRF routers** — use flat `path()` lists
- **No `app_name` namespace** — `reverse()` uses flat names like `"inventory-articles"`
- **Unmanaged models** — most models have `managed = False` (existing MySQL schema)
- **All credentials from env vars** — never hardcode DB credentials or API keys
- **OpenAPI docs** — `/api/schema/` (raw) and `/api/docs/` (Swagger UI)

---

## Common Pitfalls

- `inventory` DB uses `latin1` — don't store non-ASCII without explicit charset handling
- Adding a new app requires **both** `LOCAL_APPS` update and `config/urls.py` registration
- Migrations only apply to apps with `managed = True` models
- The chatbot can write and restart itself — always gate new write tools behind `is_staff`
