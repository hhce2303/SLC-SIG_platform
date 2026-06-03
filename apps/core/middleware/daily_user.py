"""
Middleware to attach the daily_user (from daily_users table) to every
authenticated request.

After simplejwt validates the Bearer token and sets request.user to a
django.contrib.auth.User, this middleware loads the corresponding
apps.core.models.User (daily_users row) and attaches it as
request.daily_user for use by permissions and views.

Note: Django middleware runs *before* DRF authentication, so request.user
is still AnonymousUser for JWT-protected endpoints.  We fall back to
decoding the Bearer token directly from the Authorization header.

Performance: the DailyUser lookup is cached in Redis (TTL 60 s) to avoid
one DB query per request.

Async: this middleware is async-capable. That is CRITICAL — if it were
sync-only, Django would have to adapt async views' StreamingHttpResponse to a
sync context, which buffers the async generator entirely (the SSE stream would
only flush on connection close). Being async-capable keeps the SSE path fully
async so events flush immediately.
"""

from __future__ import annotations

from typing import Callable

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

from apps.core.models import User as DailyUser

_CACHE_TTL = 60  # seconds


class DailyUserMiddleware:
    """
    Populate ``request.daily_user`` with the core.User row whose PK matches
    the authenticated user.

    Resolution order:
    1. Django session auth (``request.user``)
    2. JWT Bearer token from Authorization header
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest):
        if self._is_async:
            return self.__acall__(request)
        request.daily_user = self._build_daily_user(request)  # type: ignore[attr-defined]
        return self.get_response(request)

    async def __acall__(self, request: HttpRequest):
        # Toda la resolución (decodificar JWT + cache/DB) es sync → la corremos
        # en un thread, sin bloquear el event loop ni romper el streaming async.
        request.daily_user = await sync_to_async(  # type: ignore[attr-defined]
            self._build_daily_user, thread_sensitive=True
        )(request)
        return await self.get_response(request)

    def _build_daily_user(self, request: HttpRequest) -> DailyUser | None:
        user_pk = self._resolve_user_pk(request)
        if user_pk is None:
            return None
        return self._get_daily_user(user_pk)

    @staticmethod
    def _get_daily_user(user_pk: int) -> DailyUser | None:
        cache_key = f"daily_user:{user_pk}"
        user = cache.get(cache_key)
        if user is None:
            try:
                user = (
                    DailyUser.objects
                    .select_related("role")
                    .get(pk=user_pk)
                )
                cache.set(cache_key, user, _CACHE_TTL)
            except DailyUser.DoesNotExist:
                return None
        return user

    @staticmethod
    def _resolve_user_pk(request: HttpRequest) -> int | None:
        # 1. Django session auth (admin, browsable API, etc.)
        if hasattr(request, "user") and request.user.is_authenticated:
            return request.user.pk

        # 2. JWT from Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        try:
            from rest_framework_simplejwt.tokens import AccessToken

            token = AccessToken(auth_header[7:])  # strip "Bearer "
            return token["user_id"]
        except Exception:
            return None
