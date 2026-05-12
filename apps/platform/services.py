"""
Central platform authentication services.

Platform login does NOT require a station — it authenticates the user against
the same daily_users table and returns a JWT valid for all connected tools.
The daily-specific login (with station_id) is unaffected and continues to work
at /api/v1/auth/login/.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate

from apps.core.exceptions import ResourceNotFound, ServiceException
from apps.core.models import User as DailyUser
from apps.platform.models import Tool, UserToolAccess
from apps.platform import selectors


def platform_login(username: str, password: str) -> dict[str, Any]:
    """
    Authenticate user by username + password (no station required).

    Returns a JWT access/refresh pair plus the list of tools the user
    can access.  The JWT payload carries a ``platform=True`` claim so
    consumers can distinguish platform tokens from daily-session tokens.

    Raises:
        ServiceException – invalid credentials or user not found
    """
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.core.models import UserName

    # Resolve username → user_id (same table as daily login)
    try:
        profile = UserName.objects.get(user_name__iexact=username)
        user_id = profile.user_id
    except UserName.DoesNotExist:
        raise ServiceException("Credenciales inválidas.")

    # Authenticate via the existing DailyUserBackend
    auth_user = authenticate(user_id=user_id, password=password)
    if auth_user is None:
        raise ServiceException("Credenciales inválidas.")

    daily_user = (
        DailyUser.objects
        .select_related("role")
        .get(pk=auth_user.pk)
    )

    try:
        user_name = daily_user.profile.user_name
    except Exception:
        user_name = f"User #{daily_user.pk}"

    # Build JWT with platform-specific claims
    refresh = RefreshToken.for_user(auth_user)
    refresh["platform"] = True
    refresh["daily_user_id"] = daily_user.pk
    refresh["role"] = daily_user.role.name

    tools = get_user_tools(auth_user.pk)

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": daily_user.pk,
            "name": user_name,
            "role": daily_user.role.name,
            "role_id": daily_user.role.pk,
        },
        "tools": tools,
    }


def get_user_tools(auth_user_id: int) -> list[dict[str, Any]]:
    """
    Return the list of active tools accessible by the given user.

    Access policy:
    - If the user has at least one UserToolAccess row, return only those
      tools where is_active=True.
    - If the user has NO explicit rows, return all globally active tools
      (open-access default).
    """
    has_explicit = UserToolAccess.objects.filter(
        user_id=auth_user_id, tool__is_active=True
    ).exists()

    if has_explicit:
        accesses = (
            UserToolAccess.objects
            .filter(user_id=auth_user_id, is_active=True, tool__is_active=True)
            .select_related("tool")
            .order_by("tool__order", "tool__name")
        )
        return [_tool_payload(a.tool) for a in accesses]

    # Default: all active tools
    tools = Tool.objects.filter(is_active=True).order_by("order", "name")
    return [_tool_payload(t) for t in tools]


def get_station_config(station_number: str) -> dict[str, Any]:
    normalized_station_number = station_number.strip().upper()
    if not normalized_station_number:
        raise ServiceException("station_number es requerido.")

    station = selectors.get_station_by_number(normalized_station_number)
    if station is None:
        raise ResourceNotFound(
            f"La estación '{normalized_station_number}' no existe."
        )

    mapping = selectors.get_station_mapping(station.pk)

    return {
        "station_id": station.pk,
        "station_number": station.station_number,
        "occupied": bool(mapping and mapping.station_user_id is not None),
        "is_active": None if mapping is None or mapping.is_active is None else bool(mapping.is_active),
    }


def _tool_payload(tool: Tool) -> dict[str, Any]:
    return {
        "slug": tool.slug,
        "name": tool.name,
        "description": tool.description,
        "frontend_url": tool.frontend_url,
        "icon": tool.icon,
    }
