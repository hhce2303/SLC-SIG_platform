"""
Services — business logic for the web cookie auth system.
No logic in views or serializers.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpResponse

from django.contrib.auth.hashers import check_password
from django.db import connections

from apps.sigtools_auth import ldap_auth, token_utils
from apps.sigtools.models import SigtoolsUser
from apps.core.exceptions import ServiceException

_DB = "sigtools"

COOKIE_NAME: str = getattr(settings, "SIGTOOLS_COOKIE_NAME", "sig_token")
COOKIE_HTTPONLY: bool = getattr(settings, "SIGTOOLS_COOKIE_HTTPONLY", True)
COOKIE_SECURE: bool = getattr(settings, "SIGTOOLS_COOKIE_SECURE", False)
COOKIE_SAMESITE: str = getattr(settings, "SIGTOOLS_COOKIE_SAMESITE", "Lax")
COOKIE_MAX_AGE: int = getattr(settings, "SIGTOOLS_COOKIE_MAX_AGE", 60 * 60 * 8)   # 8 h
COOKIE_DOMAIN: str | None = getattr(settings, "SIGTOOLS_COOKIE_DOMAIN", None)
TOKEN_EXPIRY_MINUTES: int = getattr(settings, "SIGTOOLS_TOKEN_EXPIRY_MINUTES", 480)


def login(username: str, password: str) -> dict[str, Any]:
    """
    1. Try LDAP (Active Directory) authentication.
    2. If LDAP fails, fall back to local DB password (for admin-created users).
    3. Generate a Sanctum-compatible token.
    Returns { "client_token": str, "user": dict, "access_level": int }.
    Raises ServiceException on auth failure.
    """
    ldap_result = ldap_auth.ldap_authenticate(username, password)

    if ldap_result["success"]:
        # --- LDAP path (existing employees) ---
        try:
            sig_user = SigtoolsUser.objects.using(_DB).get(
                username__iexact=username,
                deleted_at__isnull=True,
            )
        except SigtoolsUser.DoesNotExist:
            try:
                sig_user = SigtoolsUser.objects.using(_DB).get(
                    email__iexact=f"{username}@{ldap_auth.LDAP_DOMAIN()}",
                    deleted_at__isnull=True,
                )
            except SigtoolsUser.DoesNotExist:
                raise ServiceException(
                    "LDAP authentication succeeded but this user has no account "
                    "in the SIG Tools system. Contact your administrator."
                )
        access_level = ldap_result["ldap_response"]
    else:
        # --- Local DB fallback (admin-created platform users) ---
        with connections[_DB].cursor() as cur:
            cur.execute(
                "SELECT id, password FROM users WHERE username = %s AND deleted_at IS NULL",
                [username],
            )
            row = cur.fetchone()

        if not row:
            raise ServiceException("Invalid credentials.")

        user_id, stored_hash = row
        if not stored_hash or not check_password(password, stored_hash):
            raise ServiceException("Invalid credentials.")

        try:
            sig_user = SigtoolsUser.objects.using(_DB).get(pk=user_id)
        except SigtoolsUser.DoesNotExist:
            raise ServiceException("Invalid credentials.")

        # Derive access_level from app_roles (any assigned role → level 1)
        from apps.installations.selectors import get_user_app_roles
        roles = get_user_app_roles(sig_user.pk)
        access_level = 1 if roles else 0
        if access_level == 0:
            raise ServiceException("Invalid credentials.")

    client_token = token_utils.generate_sanctum_token(
        user_id=sig_user.pk,
        token_name="web-platform",
        abilities=["*"],
        expires_in_minutes=TOKEN_EXPIRY_MINUTES,
    )

    return {
        "client_token": client_token,
        "user": {
            "id": sig_user.pk,
            "name": sig_user.name,
            "email": sig_user.email,
            "username": sig_user.username,
        },
        "access_level": access_level,
    }


def logout(client_token: str) -> None:
    """Revokes the token so the cookie becomes invalid on next request."""
    token_utils.revoke_token(client_token)


def set_cookie(response: HttpResponse, client_token: str) -> None:
    """Attaches the HttpOnly cookie to an outgoing response."""
    response.set_cookie(
        COOKIE_NAME,
        client_token,
        max_age=COOKIE_MAX_AGE,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
    )


def clear_cookie(response: HttpResponse) -> None:
    """Removes the cookie from the client browser."""
    response.delete_cookie(
        COOKIE_NAME,
        domain=COOKIE_DOMAIN,
        samesite=COOKIE_SAMESITE,
    )
