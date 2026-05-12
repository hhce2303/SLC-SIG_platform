"""
Token utilities — Sanctum-compatible token generation and validation.

Sanctum token format:
    plaintext  = secrets.token_hex(40)          # 80-char hex = 40 random bytes
    stored     = sha256(plaintext).hexdigest()   # 64-char hex → goes in DB
    client     = f"{db_row_id}|{plaintext}"      # this is what the client receives

This module is a port of Laravel Sanctum's PersonalAccessToken methods.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from apps.sigtools_auth.models import PersonalAccessToken

_DB = "sigtools"


def generate_sanctum_token(
    user_id: int,
    token_name: str = "web-platform",
    abilities: list[str] | None = None,
    expires_in_minutes: int | None = None,
) -> str:
    """
    Creates a Sanctum-compatible token, persists the hash in sigtools_beta,
    and returns the plaintext client token ("{id}|{plaintext}").
    The plaintext is NEVER stored.
    """
    if abilities is None:
        abilities = ["*"]

    plaintext = secrets.token_hex(40)  # 80-char hex (40 bytes)
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    expires_at: datetime | None = None
    if expires_in_minutes is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    now = datetime.now(timezone.utc)

    db_token = PersonalAccessToken.objects.using(_DB).create(
        tokenable_type="App\\Models\\User",
        tokenable_id=user_id,
        name=token_name,
        token=token_hash,
        abilities=json.dumps(abilities),
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )

    return f"{db_token.id}|{plaintext}"


def validate_token(client_token: str) -> PersonalAccessToken | None:
    """
    Validates a Bearer/cookie token received from the client.
    Mirrors Sanctum's PersonalAccessToken::findToken().
    Returns the PAT row if valid and not expired; None otherwise.
    """
    if "|" not in client_token:
        return None

    token_id_str, plaintext = client_token.split("|", 1)
    try:
        token_id = int(token_id_str)
    except ValueError:
        return None

    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    try:
        pat = PersonalAccessToken.objects.using(_DB).get(
            id=token_id,
            token=token_hash,
        )
    except PersonalAccessToken.DoesNotExist:
        return None

    # Check expiration
    if pat.expires_at is not None:
        now = datetime.now(timezone.utc)
        if pat.expires_at.tzinfo is None:
            # DB returned naive datetime — treat as UTC
            from django.utils import timezone as dj_tz
            if dj_tz.make_aware(pat.expires_at, timezone.utc) < now:
                return None
        elif pat.expires_at < now:
            return None

    # Update last_used_at (non-blocking — mirrors Sanctum behaviour)
    PersonalAccessToken.objects.using(_DB).filter(pk=pat.id).update(
        last_used_at=datetime.now(timezone.utc)
    )

    return pat


def revoke_token(client_token: str) -> bool:
    """
    Deletes a token given its plaintext form ("{id}|{plaintext}").
    Returns True if a row was deleted.
    """
    if "|" not in client_token:
        return False

    token_id_str, plaintext = client_token.split("|", 1)
    try:
        token_id = int(token_id_str)
    except ValueError:
        return False

    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    deleted, _ = PersonalAccessToken.objects.using(_DB).filter(
        id=token_id,
        token=token_hash,
    ).delete()
    return deleted > 0
