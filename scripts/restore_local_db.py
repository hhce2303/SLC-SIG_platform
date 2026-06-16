"""
Restore the latest production backup to the local MySQL Docker container.

Usage:
    python scripts/restore_local_db.py              # restore latest backup
    python scripts/restore_local_db.py <file.sql>   # restore specific file

Reads credentials from docker/.env:
    LOCAL_SIGTOOLS_DB_HOST   (default: 127.0.0.1)
    LOCAL_SIGTOOLS_DB_PORT   (default: 3307)
    LOCAL_SIGTOOLS_DB_NAME   (default: sigtools_beta)
    LOCAL_SIGTOOLS_DB_USER   (default: sigtools_user)
    LOCAL_SIGTOOLS_DB_PASSWORD

Requires the local MySQL container to be running:
    docker compose -f docker/docker-compose.dev.yml up -d
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = ROOT / "backups"


def load_env() -> dict:
    env_file = ROOT / "docker" / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    env.update(os.environ)
    return env


def pick_backup(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = ROOT / arg
        if not p.exists():
            sys.exit(f"File not found: {p}")
        return p

    dumps = sorted(BACKUPS_DIR.glob("sigtools_beta_*.sql"), reverse=True)
    if not dumps:
        sys.exit(
            f"No backups found in {BACKUPS_DIR.relative_to(ROOT)}.\n"
            "Run: python scripts/backup_db.py"
        )
    return dumps[0]


def main() -> None:
    env = load_env()

    host = env.get("LOCAL_SIGTOOLS_DB_HOST", "127.0.0.1")
    port = env.get("LOCAL_SIGTOOLS_DB_PORT", "3307")
    db = env.get("LOCAL_SIGTOOLS_DB_NAME", "sigtools_beta")
    user = env.get("LOCAL_SIGTOOLS_DB_USER", "sigtools_user")
    password = env.get("LOCAL_SIGTOOLS_DB_PASSWORD", "sigtools_pass")

    sql_file = pick_backup(sys.argv[1] if len(sys.argv) > 1 else None)

    print(f"Restoring {sql_file.name} → {db} @ {host}:{port}")
    print("Warning: this will DROP and recreate the local database.")

    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm != "y":
        sys.exit("Aborted.")

    mysql_cmd = [
        "mysql",
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        f"--password={password}",
    ]

    # Drop and recreate the database
    drop_sql = f"DROP DATABASE IF EXISTS `{db}`; CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    result = subprocess.run(
        mysql_cmd,
        input=drop_sql,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"Failed to reset database:\n{result.stderr}")

    # Restore from dump
    with sql_file.open("r", encoding="utf-8", errors="replace") as f:
        result = subprocess.run(
            mysql_cmd + [db],
            stdin=f,
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        sys.exit(f"Restore failed:\n{result.stderr}")

    print(f"Done — {db} restored from {sql_file.name}")


if __name__ == "__main__":
    main()
