# Local Development Setup

Get the full SIG Platform stack running locally in three steps. No manual Docker commands required.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | 4.x+ | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Python | 3.8+ | [python.org](https://www.python.org/downloads/) |
| Git | any | [git-scm.com](https://git-scm.com/) |

---

## Setup (3 steps)

### Step 1 — Fork & clone

Fork this repository on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-username>/SLC-SIG_platform.git
cd SLC-SIG_platform
```

### Step 2 — Initialize environment

```bash
python scripts/init_env.py
```

This will:
- Copy `.env.example` → `.env`
- Auto-generate a `SECRET_KEY`
- Wire the local Docker database variables (`SIGTOOLS_DB_HOST`, etc.)
- Tell you exactly which variables still need manual values (production DB credentials, API keys)

Edit `.env` and fill in the flagged values, then re-run the script to confirm:

```bash
python scripts/init_env.py --check-only
```

### Step 3 — Launch the stack

```bash
python app.py
```

A GUI window opens. Click **Build**, wait for completion, then click **Up**. All services start in the correct dependency order (Redis → MySQL → Django → Nginx + Poller).

---

## What runs locally

| Service | Container | Purpose |
|---------|-----------|---------|
| Redis | `SIGplatform-redis` | Cache + Channels layer |
| Django | `SIGplatform-web` | API (Gunicorn + Uvicorn, internal port 8000) |
| Nginx | `SIGplatform-nginx` | Reverse proxy, static files, TLS termination |
| Poller | `SIGplatform-poller` | Background realtime polling task |
| MySQL | `SIGplatform-sigtools-db` | Local sigtools_beta DB mirror (host port 3307) |

The stack is accessed at **http://localhost** (port 80 by default, configurable via `NGINX_PORT` in `.env`).

Django health check endpoint: `http://localhost/api/v1/health/`

---

## GUI Button Reference

| Button | What it does |
|--------|-------------|
| **Build** | `docker compose build` — rebuilds images after code changes |
| **Up** | `docker compose up -d` — starts all services (idempotent, safe to run anytime) |
| **Restart** | `docker compose restart` — restarts all running containers |
| **Nginx Restart** | `docker compose restart nginx` — reloads Nginx config without touching other services |
| **Health Status** | Prints current state and health of every container to the Output pane |
| **Logs** | `docker compose logs -f` — streams live logs from all services (click **⏹ Stop** to exit) |
| **Down** | `docker compose down` — stops and removes containers (volumes are preserved) |

Clicking buttons in any order is safe — wrong-order clicks show an error in the Output pane but won't crash the stack or corrupt data.

---

## Local MySQL database

The local `sigtools_beta` database runs on **port 3307** (not 3306) to avoid conflicts with any MySQL already installed on your machine.

Connect from any MySQL client:

```
Host:     localhost
Port:     3307
Database: sigtools_beta
User:     sigtools_user
Password: sigtools_pass   ← override via LOCAL_SIGTOOLS_DB_PASSWORD in .env
```

To seed it from a production dump, use the restore script:

```bash
python scripts/restore_local_db.py
```

---

## Adding seed SQL

Place `.sql` files in `docker/init-db/`. They run automatically the first time the MySQL container starts (before Django connects). Files execute in filename order — prefix with `01_`, `02_`, etc. to control order.

---

## Rebuilding after dependency changes

If you add a package to `requirements/`:

1. Click **Build** in the GUI
2. Click **Up** once the build finishes

The `--no-cache` build is only needed if a base image changed. For routine dependency updates the cache build is faster and correct.

---

## Troubleshooting

**"Docker Desktop is not running"**
Start Docker Desktop and wait for the whale icon to stop animating, then re-run `app.py`.

**`web` container shows `● unhealthy`**
Run **Logs** and look for Python errors. Common causes: missing `.env` values, database not reachable, missing migrations (`docker compose exec web python manage.py migrate`).

**Port 80 already in use**
Set `NGINX_PORT=8080` (or any free port) in your `.env`, then click **Down** → **Up**.

**MySQL keeps restarting**
The MySQL container needs ~30 seconds on first start (InnoDB initialization). The Django container waits for it via the health check. Check **Health Status** — if MySQL shows `◐ starting` that is normal; it will become `● healthy` shortly.

**"Compose file not found"**
Make sure `app.py` is in the repository root (same level as the `docker/` folder).

---

## Production deploy reminder

The local stack uses `docker-compose.local.yml` as an overlay. For production, use only the base:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Never use `docker-compose.local.yml` in production — it exposes the MySQL port on the host and uses weak default passwords.
