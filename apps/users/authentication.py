"""
Decoupled JWT authentication for the daily-log domain (operators + platform).

Unlike the deleted DailyUserBackend, no django.contrib.auth.User is involved
at all: the token carries a daily_user_id claim resolved directly against
apps.core.models.User (the daily_users legacy table). Pattern mirrors
apps.sigtools_auth.authentication.SigtoolsCookieAuthentication /
SigtoolsWebUser -- the platform's only prior precedent for JWT/token auth
that doesn't depend on auth.User.

See docs/arc42/daily/decisions/0001-jwt-desacoplado-de-usuarios-django.md.

IMPORTANT: DailyJWTAuthentication MUST be listed BEFORE
rest_framework_simplejwt.authentication.JWTAuthentication in
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]. A DailyAccessToken never
carries the generic "user_id" claim, so if the generic JWTAuthentication runs
first it raises InvalidToken (missing claim) before this authenticator ever
gets a chance to run -- DRF's authentication chain stops on a raised
exception, it does not fall through to the next authenticator.
"""

from __future__ import annotations

from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import User as DailyUser

_CACHE_TTL = 60  # seconds -- same key format/TTL as DailyUserMiddleware


class DailyAccessToken(AccessToken):
    """
    Same token_type ("access") as stock AccessToken -- only the default
    lifetime differs, and services.issue_daily_access_token() always
    re-reads settings.DAILY_JWT["ACCESS_TOKEN_LIFETIME"] fresh at issuance
    time rather than relying on this class attribute (SimpleJWT bakes
    `lifetime` in at class-body/import time, which is fine in production
    but a known footgun for tests using override_settings).
    """


class DailyJWTUser:
    """
    Lightweight, non-Django-model user returned by DailyJWTAuthentication.
    Wraps an apps.core.models.User (daily_users row) so IsAuthenticated /
    request.user.pk work without a django.contrib.auth.User instance.
    Mirrors apps.sigtools_auth.authentication.SigtoolsWebUser.
    """

    is_authenticated: bool = True
    is_anonymous: bool = False
    is_staff: bool = False

    def __init__(self, daily_user: DailyUser) -> None:
        self._user = daily_user
        self.pk = daily_user.pk
        self.id = daily_user.pk

    @property
    def daily_user(self) -> DailyUser:
        return self._user

    @property
    def role(self):
        return self._user.role

    def __str__(self) -> str:
        return str(self._user)


def get_daily_user_cached(user_pk: int) -> DailyUser | None:
    """
    Cache-aside lookup, same key format/TTL as DailyUserMiddleware, so
    whichever of the two resolves identity first on a given request warms
    the entry for the other instead of doubling the DB hit.
    """
    cache_key = f"daily_user:{user_pk}"
    user = cache.get(cache_key)
    if user is None:
        try:
            user = DailyUser.objects.select_related("role").get(pk=user_pk)
        except DailyUser.DoesNotExist:
            return None
        cache.set(cache_key, user, _CACHE_TTL)
    return user


class DailyJWTAuthentication(BaseAuthentication):
    """
    Resolves a Bearer token issued by apps.users.services.login() /
    apps.platform.services.platform_login() directly against daily_users,
    with no django.contrib.auth.User involved.

    - No/garbled Bearer header             -> None   (try next authenticator)
    - Decodable but no daily_user_id claim -> None   (not ours -- e.g. a
      token from a different JWT consumer sharing the same SECRET_KEY)
    - daily_user_id claim present but the user row is gone -> AuthenticationFailed
      (this token positively identifies as ours; no other authenticator
      could resolve it differently, so a hard 401 is correct here)
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        raw_token = auth_header[7:].strip()
        if raw_token.count(".") != 2:
            return None  # not JWT-shaped at all

        try:
            token = DailyAccessToken(raw_token)
        except TokenError:
            return None  # malformed/expired/wrong-type -- defer to the next authenticator

        daily_user_id = token.payload.get("daily_user_id")
        if daily_user_id is None:
            return None  # syntactically valid access token, but not ours

        daily_user = get_daily_user_cached(daily_user_id)
        if daily_user is None:
            raise AuthenticationFailed("User no longer exists.")

        return (DailyJWTUser(daily_user), token)

    def authenticate_header(self, request) -> str:
        return "Bearer"
