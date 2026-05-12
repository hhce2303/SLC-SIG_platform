"""
DRF authentication class for the Sigtools cookie-based auth system.

Cookie name:  sig_token  (HttpOnly, set by LoginView)
Reads:        HttpOnly cookie → validates against personal_access_tokens (sigtools_beta)
Returns:      (SigtoolsWebUser, pat_instance) — or None if no cookie present

SigtoolsWebUser is a thin, non-Django-model wrapper so that DRF's
IsAuthenticated permission (which checks request.user.is_authenticated)
works without needing a full contrib.auth.User object.

This authenticator is added to DEFAULT_AUTHENTICATION_CLASSES alongside
JWTAuthentication. DRF tries each in order — the cookie auth runs first;
if the cookie is absent it returns None and DRF falls through to JWT.
This means DailyLog JWT endpoints are completely unaffected.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.sigtools_auth import token_utils
from apps.sigtools_auth.models import PersonalAccessToken

COOKIE_NAME = getattr(settings, "SIGTOOLS_COOKIE_NAME", "sig_token")

_DB = "sigtools"


class SigtoolsWebUser:
    """
    Lightweight user object returned by SigtoolsCookieAuthentication.
    Wraps a SigtoolsUser ORM row and exposes is_authenticated for DRF.
    """
    is_authenticated: bool = True
    is_anonymous: bool = False
    is_staff: bool = False  # Sigtools users are not Django admin staff

    def __init__(self, sigtools_user) -> None:
        self._user = sigtools_user
        self.pk = sigtools_user.pk
        self.id = sigtools_user.pk

    # Proxy common attributes so views can use request.user.name etc.
    @property
    def name(self) -> str:
        return self._user.name

    @property
    def email(self) -> str:
        return self._user.email

    @property
    def username(self) -> str | None:
        return self._user.username

    @property
    def sigtools_user(self):
        return self._user

    def __str__(self) -> str:
        return self._user.name


class SigtoolsCookieAuthentication(BaseAuthentication):
    """
    Resolves the sig_token from two sources (in priority order):
      1. HttpOnly cookie ``sig_token``          ← browser web client
      2. ``Authorization: Bearer <token>`` header ← API clients / mobile

    - Token absent   → return None (DRF continues to next authenticator)
    - Token invalid  → raise AuthenticationFailed (request rejected)
    - Token valid    → return (SigtoolsWebUser, pat)
    """

    def authenticate(self, request):
        # Source 1: HttpOnly cookie (browser)
        client_token = request.COOKIES.get(COOKIE_NAME)

        # Source 2: Authorization: Bearer header (API clients)
        if not client_token:
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                client_token = auth_header[7:].strip()

        if not client_token:
            return None  # No token → try next authenticator

        pat: PersonalAccessToken | None = token_utils.validate_token(client_token)
        if pat is None:
            raise AuthenticationFailed("Invalid or expired session cookie.")

        # Load the SigtoolsUser (from apps.sigtools.models — same DB)
        from apps.sigtools.models import SigtoolsUser
        try:
            sig_user = SigtoolsUser.objects.using(_DB).get(pk=pat.tokenable_id)
        except SigtoolsUser.DoesNotExist:
            raise AuthenticationFailed("User associated with this token no longer exists.")

        return (SigtoolsWebUser(sig_user), pat)

    def authenticate_header(self, request) -> str:
        """Returned in WWW-Authenticate header on 401."""
        return "Cookie"
