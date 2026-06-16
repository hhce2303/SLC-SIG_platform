# Contributing — SIG-SLC Platform

## Branch Strategy

```
main          → production. Protected. Never push directly.
develop       → integration. Protected. Never push directly.
feature/*     → new features. Branch from develop. PR → develop.
hotfix/*      → urgent fixes. Branch from main. PR → main AND develop.
testing/*     → QA branches. Branch from develop. Not merged to main directly.
```

### Start a new feature

```bash
git checkout develop && git pull origin develop
git checkout -b feature/<descriptive-name>
# ... work ...
git push origin feature/<descriptive-name>
# Open PR: feature/<name> → develop
```

### Start a hotfix

```bash
git checkout main && git pull origin main
git checkout -b hotfix/<issue>
# ... smallest possible fix ...
git push origin hotfix/<issue>
# Open PR → main; after merge, open second PR → develop
```

## Commit Convention

```
<type>(<scope>): <description>

Types : feat | fix | chore | docs | refactor | test | hotfix
Scopes: installations | sigtools | auth | docker | db | scripts | config
```

Examples:
```
feat(installations): add visual_metadata column to installations table
fix(docker): replace mariadb with mysql:8.0 in dev compose
chore(scripts): add production DB backup and local restore scripts
```

- Imperative mood, max 72 chars, no trailing period.

## Pull Request Requirements

Every PR must state:
1. **What** — one-line description (PR title)
2. **Why** — motivation or ticket reference
3. **DB changes** — list any schema changes and migration file names
4. **Test plan** — steps to verify

## Database Change Policy

> **Never modify the production DB without explicit authorization from the project lead.**

Checklist before any schema change:

- [ ] Backup taken: `python scripts/backup_db.py`
- [ ] Tested on local MySQL Docker (port 3307)
- [ ] Migration file created via `manage.py makemigrations`
- [ ] Rollback procedure documented in the PR
- [ ] Authorization received from project lead
- [ ] `docs/levantamiento_requerimientos_cambios_sigtoolsbeta.md` updated

## Local Dev Environment

```bash
# Start local MySQL mirror
docker compose -f docker/docker-compose.dev.yml up -d

# Take a fresh backup of production
python scripts/backup_db.py

# Restore latest backup to local
python scripts/restore_local_db.py
```

Credentials live in `docker/.env` (gitignored — never commit it).

## What Is Forbidden

- Direct push to `main` or `develop`
- `git push --force` on any shared branch
- Committing `docker/.env`, `.env`, or any file with credentials
- Committing SQL dumps (kept in `backups/`, which is gitignored)
- MariaDB-specific SQL in migration files — the platform targets MySQL 8.0
- Applying migrations to production without a prior backup
