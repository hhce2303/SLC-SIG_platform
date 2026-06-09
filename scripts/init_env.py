#!/usr/bin/env python3
"""
SIG Platform — Local Environment Setup Wizard

Prepares a new developer machine for running the local Docker stack.
Run this once after cloning/forking the repository.

Usage:
    python scripts/init_env.py
    python scripts/init_env.py --check-only   # validate without writing
    python scripts/init_env.py --force        # overwrite existing .env
"""

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
ENV_FILE = REPO_ROOT / ".env"

# Variables that init_env auto-fills for the local Docker stack.
# All others remain as placeholders for the developer to fill manually.
LOCAL_DEFAULTS = {
    "SIGTOOLS_DB_HOST":     "sigtools-db",     # Docker service name (internal DNS)
    "SIGTOOLS_DB_PORT":     "3306",
    "LOCAL_SIGTOOLS_DB_NAME":     "sigtools_beta",
    "LOCAL_SIGTOOLS_DB_USER":     "sigtools_user",
    "LOCAL_SIGTOOLS_DB_PASSWORD": "sigtools_pass",
    "LOCAL_SIGTOOLS_ROOT_PASSWORD": "localroot",
    "LOCAL_SIGTOOLS_DB_PORT":     "3307",
    "REDIS_URL":            "redis://redis:6379/0",
    "DOCKER_CONTAINER_NAME": "SIGplatform-web",
    "DJANGO_ENV":           "production",
    "DEBUG":                "False",
}

# Keys that MUST be manually set — we warn if they still hold their placeholder value.
REQUIRED_MANUAL = [
    "SECRET_KEY",
    "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST",
]

PLACEHOLDER_PATTERNS = [
    "your_",
    "change-this",
    "your-api-key",
    "your-azure",
]


def is_placeholder(value: str) -> bool:
    return any(p in value.lower() for p in PLACEHOLDER_PATTERNS)


def check_docker() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_python() -> bool:
    return sys.version_info >= (3, 8)


def generate_secret_key(length: int = 60) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_env(force: bool = False) -> bool:
    if ENV_FILE.exists() and not force:
        print(f"  .env already exists — skipping copy (use --force to overwrite)")
        return False

    if not ENV_EXAMPLE.exists():
        print("  ERROR: .env.example not found in repository root.", file=sys.stderr)
        sys.exit(1)

    shutil.copy(ENV_EXAMPLE, ENV_FILE)
    print(f"  Created {ENV_FILE}")
    return True


def patch_env():
    """Inject local-stack defaults and a fresh SECRET_KEY into .env."""
    content = ENV_FILE.read_text(encoding="utf-8")

    # Auto-generate SECRET_KEY if still a placeholder
    if re.search(r"^SECRET_KEY=change-this", content, re.MULTILINE):
        new_key = generate_secret_key()
        content = re.sub(
            r"^(SECRET_KEY=).*$", rf"\g<1>{new_key}",
            content, flags=re.MULTILINE
        )
        print("  Generated new SECRET_KEY")

    for key, value in LOCAL_DEFAULTS.items():
        pattern = rf"^({re.escape(key)}=).*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)
        else:
            # Key not in template — append it
            content += f"\n{key}={value}"

    ENV_FILE.write_text(content, encoding="utf-8")
    print(f"  Patched {len(LOCAL_DEFAULTS)} local-stack variables")


def validate_env() -> list:
    """Return list of (key, issue) tuples for unfilled required vars."""
    content = ENV_FILE.read_text(encoding="utf-8")
    issues = []
    for key in REQUIRED_MANUAL:
        match = re.search(rf"^{re.escape(key)}=(.*)$", content, re.MULTILINE)
        if not match:
            issues.append((key, "not found in .env"))
        elif not match.group(1).strip():
            issues.append((key, "empty"))
        elif is_placeholder(match.group(1)):
            issues.append((key, f"still a placeholder: {match.group(1)[:40]}"))
    return issues


def print_banner(title: str):
    width = 60
    print("\n" + "─" * width)
    print(f"  {title}")
    print("─" * width)


def main():
    parser = argparse.ArgumentParser(description="SIG Platform local environment setup")
    parser.add_argument("--check-only", action="store_true",
                        help="Validate .env without writing anything")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing .env with a fresh copy")
    args = parser.parse_args()

    print_banner("SIG Platform — Local Environment Setup")

    # ── Prerequisites ──────────────────────────────────────────
    print("\n[1/4] Checking prerequisites...")

    if not check_python():
        print(f"  ERROR: Python 3.8+ required (found {sys.version})", file=sys.stderr)
        sys.exit(1)
    print(f"  Python {sys.version.split()[0]} ✓")

    docker_ok = check_docker()
    if docker_ok:
        print("  Docker Desktop running ✓")
    else:
        print("  WARNING: Docker Desktop is not running.")
        print("           Start it before running app.py or docker compose commands.")

    # ── .env file ──────────────────────────────────────────────
    print("\n[2/4] Setting up .env file...")

    if args.check_only:
        if not ENV_FILE.exists():
            print("  .env not found — run init_env.py (without --check-only) to create it.")
            sys.exit(1)
    else:
        created = create_env(force=args.force)
        if created or args.force:
            patch_env()
        else:
            print("  Re-patching local-stack defaults into existing .env...")
            patch_env()

    # ── Validation ─────────────────────────────────────────────
    print("\n[3/4] Validating required variables...")
    issues = validate_env()

    if issues:
        print("  The following variables need manual values in .env:")
        for key, reason in issues:
            print(f"    ✗  {key}  ({reason})")
        print()
        print(f"  Edit {ENV_FILE} and fill in the values above,")
        print("  then run this script again or proceed to app.py.")
    else:
        print("  All required variables are set ✓")

    # ── Next steps ─────────────────────────────────────────────
    print("\n[4/4] Next steps:")
    if issues:
        print("  1. Edit .env and fill in the missing values listed above")
        print("  2. Run: python app.py")
    else:
        print("  1. Run: python app.py")
        print("  2. Click  Build  → then  Up")
        print("  3. Watch the Output pane — stack is ready when all services show ● healthy")

    if issues:
        print("\n" + "─" * 60)
        print("  Setup incomplete — .env needs manual edits")
        sys.exit(2)
    else:
        print("\n" + "─" * 60)
        print("  Setup complete! Run: python app.py")

    print()


if __name__ == "__main__":
    main()
