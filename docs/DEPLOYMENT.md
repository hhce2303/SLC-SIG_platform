# SIGplatform — Deployment Guide

## Production Environment

| Item | Value |
|---|---|
| **Server** | MKS Server |
| **Server IP** | `192.168.1.69` |
| **API Base URL** | `http://192.168.1.69/api/v1/` |
| **Admin** | `http://192.168.1.69/admin/` |
| **Stack path** | `C:\Users\jjacome\Documents\GitHub\SLC-SIG_platform` |
| **Stack file** | `docker/docker-compose.yml` |
| **Web container** | `SIGplatform-web` |

---

## Prerequisites

- Docker Engine ≥ 24 and Docker Compose v2
- The user running Docker must be in the `docker` group (or run as root)
- Ports 80 (nginx) accessible on the host
- Network access to the MySQL databases defined in `.env`

## First-Time Setup on a New Server

### 1. Clone / copy the project

```bash
git clone https://github.com/hhce2303/SLC-SIG_platform.git SIGplatform
cd SIGplatform
```

### 2. Create the environment file

```bash
cp .env.example .env
nano .env        # fill in all values (see comments in the file)
```

**Critical values to set:**
| Variable | Description |
|---|---|
| `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | Server IP + domain, comma-separated |
| `DB_*` / `SIGTOOLS_DB_*` | Remote MySQL credentials |
| `INVENTORY_DB_*` / `SCHEDULES_DB_*` | LAN MySQL credentials |
| `ANTHROPIC_API_KEY` | Required for the chatbot |
| `MS_GRAPH_*` | Required for email notifications |
| `DOCKER_CONTAINER_NAME` | Must be `SIGplatform-web` (matches docker-compose.yml) |
| `CORS_ALLOWED_ORIGINS` | Frontend URL(s) |

### 3. Build and start the stack

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

This will:
- Build the Django image (installs all Python dependencies)
- Run `python manage.py migrate` automatically on startup
- Run `python manage.py collectstatic` automatically on startup
- Start nginx on port 80, Redis, the web worker, and the realtime poller

### 4. Verify the stack

```bash
# All 4 containers should be running
docker compose -f docker/docker-compose.yml ps

# Check web logs
docker logs SIGplatform-web --tail 50

# Health check
curl http://localhost/api/v1/health/
```

---

## Routine Operations

### Deploy code changes (no Dockerfile change)

```powershell
# Windows example — copy a changed file into the running container and restart
docker cp apps\<app>\<file>.py SIGplatform-web:/app/apps/<app>/<file>.py
docker compose -f docker\docker-compose.yml restart web
```

### Full rebuild (Dockerfile or requirements changed)

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

### View logs

```bash
docker logs SIGplatform-web -f
docker logs SIGplatform-nginx -f
docker logs SIGplatform-poller -f
```

### Run a management command

```bash
docker exec SIGplatform-web python manage.py <command>
```

---

## CI/CD — Auto-deploy (GitHub Actions)

Pushes to `main` deploy automatically. There are **two targets**, each running on its own
self-hosted Windows runner:

| Target | Runner label | Stack | Compose files |
|---|---|---|---|
| `local` | `local` | this PC — local production mirror | `docker-compose.yml` + `docker-compose.local.yml` |
| `mks` | `mks` | MKS server `192.168.1.69` — production | `docker-compose.yml` |

Both call the reusable workflow [`.github/workflows/deploy-target.yml`](../.github/workflows/deploy-target.yml)
from [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml), so the steps
(sync → build → **pytest gate** → up → conditional nginx restart → health) live in one place.

### Why self-hosted runners

MKS (`192.168.1.69`) is on a private LAN that GitHub's cloud runners cannot reach, and images are
built from source on each machine (no registry). Each runner operates directly on its own stack
checkout so `.env` (gitignored) and the named volumes (`media_data`, `mirror_db_data`) keep their
identity. No GitHub Secrets are required — only repository **Variables**.

### Repository variables (Settings → Secrets and variables → Actions → Variables)

| Variable | Purpose |
|---|---|
| `STACK_DIR_LOCAL` | Absolute path to the stack checkout on this PC's runner. Until set, the `local` job is skipped. |
| `STACK_DIR_MKS` | Absolute path to the stack checkout on the MKS runner. |
| `MKS_ENABLED` | Set to `true` **only once the MKS runner is configured**. Default: the `mks` job stays skipped (grey, not failed). |
| `LOCAL_ENABLED` | Set to `false` to disable the `local` target. Default: on. |

### One-time runner setup (per machine)

1. In GitHub: **Repo → Settings → Actions → Runners → New self-hosted runner** (Windows x64).
2. When configuring (`config.cmd`), add a **unique label**: `local` for this PC, `mks` for the
   MKS server. The defaults `self-hosted` + `windows` are added automatically.
3. Install it **as a service** so it survives reboots. The service account must run `docker compose`,
   have read/write on the stack directory, and have `git` on its `PATH`.
4. Use a **dedicated deploy checkout that tracks `main`** as the stack directory (not your active
   dev working tree) — the sync step runs `git checkout -f -B main origin/main` + `git reset --hard`,
   which discards tracked local changes. Untracked files (`.env`, `docker/init-db/*.sql`) are kept.
   The local mirror's `mirror_db_data` volume is shared by Compose project name `docker`, so it
   persists across checkouts (seed it once per [LOCAL_MIRROR.md](LOCAL_MIRROR.md)).
5. Set the matching `STACK_DIR_*` variable to that path.

### What each deploy does

| Step | Action |
|---|---|
| Sync | `git fetch` + `git checkout -f -B main origin/main` + `git reset --hard` in the stack dir |
| Detect | computes changed files to decide whether nginx needs a restart |
| Build | `docker compose build` (does not disrupt running containers) |
| Test gate | runs `python -m pytest` (SQLite) in an ephemeral container; **aborts the deploy if tests fail** |
| Deploy | `docker compose up -d` (migrations run via `entrypoint.sh`) |
| nginx | `restart nginx` **only** when `docker/nginx.conf/**` changed (bind-mounted config) |
| Health | retries `GET /api/v1/health/` on the `web` container, then prints `ps` |

Trigger manually anytime via **Actions → Deploy → Run workflow** (`workflow_dispatch`).

---

## Architecture Notes

- **nginx** (port 80) → reverse-proxies to **web** (port 8000, internal only)
- **web** uses Gunicorn + UvicornWorker (4 workers, ASGI)
- **poller** runs the realtime event poller (`run_realtime_poller`)
- **redis** is used for pub/sub realtime events
- No code is mounted as a volume — all `.py` changes require `docker cp` + restart, or a full rebuild

### Docker socket access

The `web` container mounts `/var/run/docker.sock` to allow the chatbot's `restart_service` tool to restart itself. The `django` user inside the container is added to the `root` group in the Dockerfile for this purpose.

On the new server, ensure the Docker socket is at `/var/run/docker.sock` (standard location on Linux).

---

## nginx Configuration

Config file: `docker/nginx.conf/default.conf`

- All traffic on port 80 is proxied to `web:8000`
- `/api/` — SSE-safe (buffering off, long timeout, `Connection: ""` header)
- `/web-auth/` — standard proxy for Django session auth pages

To add HTTPS (recommended for production):
1. Obtain an SSL certificate (Let's Encrypt / Certbot)
2. Add port `443:443` to the nginx service in `docker-compose.yml`
3. Update `docker/nginx.conf/default.conf` with SSL directives

---

## Databases

This backend connects to **4 separate MySQL databases**. All must be accessible from the server where Docker runs:

| Key | DB | Typical location |
|---|---|---|
| `default` | `sig_dailylogs` | Remote host (`DB_HOST`) |
| `sigtools` | `sigtools_beta` | Same as `DB_HOST` |
| `inventory` | Inventory DB | LAN host (`INVENTORY_DB_HOST`) |
| `schedules` | `slc_schedules` | LAN host (`SCHEDULES_DB_HOST`) |

> Only `default` and `sigtools` databases are managed by Django migrations.  
> `inventory` and `schedules` use `managed = False` models (read-only from Django's perspective).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `SIGplatform-web` stays `unhealthy` | Migration or collectstatic failed | `docker logs SIGplatform-web` |
| 502 Bad Gateway | `web` not healthy yet | Wait for healthcheck to pass (up to 15s) |
| DB connection error | Wrong host/port/credentials in `.env` | Double-check `DB_HOST`, firewall rules |
| Chatbot `restart_service` fails | Socket permission | Add deploy user to `docker` group |
| Emails not sending | MS Graph not configured | Fill `MS_GRAPH_*` vars in `.env` |
