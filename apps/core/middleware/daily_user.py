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
"""

from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.models import User as DailyUser


class DailyUserMiddleware:
    """
    Populate ``request.daily_user`` with the core.User row whose PK matches
    the authenticated user.

    Resolution order:
    1. Django session auth (``request.user``)
    2. JWT Bearer token from Authorization header
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.daily_user = None  # type: ignore[attr-defined]

        user_pk = self._resolve_user_pk(request)
        if user_pk is not None:
            try:
                request.daily_user = (  # type: ignore[attr-defined]
                    DailyUser.objects
                    .select_related("role")
                    .get(pk=user_pk)
                )
            except DailyUser.DoesNotExist:
                pass

        return self.get_response(request)

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
