"""
Dump production sigtools_beta to a timestamped SQL file under backups/.

Usage:
    python scripts/backup_db.py

Reads credentials from environment variables (set in docker/.env or your shell):
    SIGTOOLS_DB_HOST, SIGTOOLS_DB_PORT, SIGTOOLS_DB_NAME,
    SIGTOOLS_DB_USER, SIGTOOLS_DB_PASSWORD

Output: backups/sigtools_beta_YYYYMMDD_HHMMSS.sql
"""

import os
import subprocess
import sys
from datetime import datetime
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


def main() -> None:
    env = load_env()

    host = env.get("SIGTOOLS_DB_HOST", "72.167.56.142")
    port = env.get("SIGTOOLS_DB_PORT", "3306")
    db = env.get("SIGTOOLS_DB_NAME", "sigtools_beta")
    user = env.get("SIGTOOLS_DB_USER") or env.get("SIGTOOLS_DB_USER_BETA")
    password = env.get("SIGTOOLS_DB_PASSWORD") or env.get("SIGTOOLS_DB_PASSWORD_BETA")

    if not user or not password:
        sys.exit(
            "Error: SIGTOOLS_DB_USER and SIGTOOLS_DB_PASSWORD must be set.\n"
            "Add them to docker/.env or export them in your shell."
        )

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = BACKUPS_DIR / f"sigtools_beta_{timestamp}.sql"

    cmd = [
        "mysqldump",
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        f"--password={password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--set-gtid-purged=OFF",
        db,
    ]

    print(f"Backing up {db} @ {host}:{port} → {out_file.relative_to(ROOT)}")

    with out_file.open("w", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        out_file.unlink(missing_ok=True)
        sys.exit(f"mysqldump failed:\n{result.stderr}")

    size_kb = out_file.stat().st_size // 1024
    print(f"Done — {size_kb} KB written to {out_file.name}")


if __name__ == "__main__":
    main()
