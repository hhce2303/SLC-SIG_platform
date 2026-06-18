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

Pushes to `main` deploy automatically via [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).
The workflow runs the same steps as *Routine Operations* but unattended: it syncs the code
in-place, builds the image, runs a **pytest gate**, recreates the containers, restarts nginx
only if its config changed, and health-checks the result.

### Why a self-hosted runner

MKS (`192.168.1.69`) is on a private LAN that GitHub's cloud runners cannot reach. The workflow
therefore runs on a **self-hosted runner installed on MKS itself**, operating directly on the
stack at `C:\Users\jjacome\Documents\GitHub\SLC-SIG_platform` so that `.env` (gitignored) and the
named `media_data` volume are preserved. No GitHub Secrets are required.

### One-time runner setup on MKS

1. In GitHub: **Repo → Settings → Actions → Runners → New self-hosted runner** (Windows x64).
   Follow the download/configure commands shown there.
2. Add the label `windows` when prompted (the workflow targets `runs-on: [self-hosted, windows]`).
3. Install it **as a service** (`./svc.sh install` / the `Install` step of `config.cmd`) so it
   survives reboots. The service account must:
   - have access to Docker Desktop (be able to run `docker compose`),
   - have read/write on `C:\Users\jjacome\Documents\GitHub\SLC-SIG_platform`,
   - have `git` on its `PATH`.
4. Ensure that stack directory has the production `.env` present and a clean working tree
   (the workflow runs `git reset --hard origin/main`, discarding uncommitted local changes).

### What the workflow does

| Step | Action |
|---|---|
| Sync | `git fetch` + `git reset --hard origin/main` in-place |
| Detect | computes changed files to decide whether nginx needs a restart |
| Build | `docker compose build` (does not disrupt running containers) |
| Test gate | runs `pytest` in an ephemeral container; **aborts the deploy if tests fail** |
| Deploy | `docker compose up -d` (migrations run via `entrypoint.sh`) |
| nginx | `restart nginx` **only** when `docker/nginx.conf/**` changed (bind-mounted config) |
| Health | retries `GET /api/v1/health/` on the `web` container, then prints `ps` |

Trigger it manually anytime via **Actions → Deploy to MKS → Run workflow** (`workflow_dispatch`).

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
