"""
Custom authentication backend for daily_users table.

The legacy database stores plain-text passwords in daily_users.user_password.
This backend validates credentials against that table and returns a Django
contrib.auth User (created/synced on-the-fly) so simplejwt can issue tokens.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User as AuthUser
from django.http import HttpRequest

from apps.core.models import User as DailyUser


class DailyUserBackend(BaseBackend):
    """
    Authenticate against daily_users using plain-text password comparison.

    On success, returns (or creates) a mirrored django.contrib.auth.User so
    that simplejwt can generate tokens with a proper user_id.  The auth.User
    is kept in sync as a thin mirror — the real source of truth stays in
    daily_users.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        user_id: int | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> AuthUser | None:
        if user_id is None or password is None:
            return None

        try:
            daily_user = (
                DailyUser.objects.select_related("role")
                .get(pk=user_id)
            )
        except DailyUser.DoesNotExist:
            return None

        # Plain-text comparison (legacy DB — passwords are NOT hashed)
        if daily_user.password != password:
            return None

        # Sync to django.contrib.auth.User for JWT token issuance
        auth_user, _ = AuthUser.objects.get_or_create(
            pk=daily_user.pk,
            defaults={
                "username": f"daily_{daily_user.pk}",
                "is_active": True,
            },
        )

        return auth_user

    def get_user(self, user_id: int) -> AuthUser | None:
        try:
            return AuthUser.objects.get(pk=user_id)
        except AuthUser.DoesNotExist:
            return None
