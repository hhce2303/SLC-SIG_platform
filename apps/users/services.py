"""
Authentication & session management services.

Ports the following functions from proyecto_app:
  - authenticate_user()  → login()
  - new_sesion_entry()   → _create_session()
  - do_logout()          → logout()
  - free_station()       → _free_station()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import (
    ConflictError,
    ResourceNotFound,
    ServiceException,
)
from apps.core.models import StationMap, User as DailyUser
from apps.users.models import Session


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(username: str, password: str, station_id: int) -> dict[str, Any]:
    """
    Authenticate user by name, claim station, create BD session, return JWT tokens.

    Raises:
        ServiceException – invalid credentials or user not found
        ConflictError    – station already occupied or user already logged in
    """
    from apps.core.models import UserName

    # Resolve username -> user_id via daily_users_names
    try:
        profile = UserName.objects.get(user_name__iexact=username)
        user_id = profile.user_id
    except UserName.DoesNotExist:
        raise ServiceException("Credenciales inválidas.")

    auth_user = authenticate(user_id=user_id, password=password)
    if auth_user is None:
        raise ServiceException("Credenciales inválidas.")

    daily_user = (
        DailyUser.objects
        .select_related("role")
        .get(pk=auth_user.pk)
    )

    with transaction.atomic():
        # Check user doesn't already have an active session
        if Session.objects.filter(user_id=daily_user.pk, sesion_active=1).exists():
            raise ConflictError("El usuario ya tiene una sesión activa.")

        # Claim station
        _claim_station(daily_user.pk, station_id)

        # Create BD session
        session = _create_session(daily_user.pk, station_id)

    # Issue JWT tokens
    refresh = RefreshToken.for_user(auth_user)
    refresh["daily_user_id"] = daily_user.pk
    refresh["role"] = daily_user.role.name

    try:
        user_name = daily_user.profile.user_name
    except Exception:
        user_name = f"User #{daily_user.pk}"

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": daily_user.pk,
            "name": user_name,
            "role": daily_user.role.name,
            "role_id": daily_user.role.pk,
        },
        "session_id": session.pk,
        "station_id": station_id,
    }


def _claim_station(user_id: int, station_id: int) -> None:
    """Assign station to user. Raises ConflictError if already occupied."""
    try:
        mapping = StationMap.objects.select_for_update().get(station_id=station_id)
    except StationMap.DoesNotExist:
        raise ResourceNotFound(f"Estación {station_id} no encontrada.")

    if mapping.station_user_id is not None:
        raise ConflictError(
            f"La estación {station_id} ya está ocupada por el usuario {mapping.station_user_id}."
        )

    mapping.station_user_id = user_id
    mapping.save(update_fields=["station_user_id"])


def _create_session(user_id: int, station_id: int) -> Session:
    """Insert a new active session row in daily_sesions."""
    return Session.objects.create(
        user_id=user_id,
        station_id=station_id,
        sesion_in=timezone.now(),
        sesion_active=1,
        sesion_status=0,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout(daily_user: DailyUser, refresh_token: str | None = None) -> None:
    """
    Close active BD session, free station, and blacklist the refresh token.

    Runs in a single transaction to keep BD consistent.
    """
    with transaction.atomic():
        _close_session(daily_user.pk)
        _free_station(daily_user.pk)

    # Blacklist refresh token (outside transaction — token store may be separate)
    if refresh_token:
        _blacklist_token(refresh_token)


def _close_session(user_id: int) -> None:
    """Set sesion_out and sesion_active=0 on the current active session."""
    updated = Session.objects.filter(
        user_id=user_id,
        sesion_active=1,
    ).update(
        sesion_out=timezone.now(),
        sesion_active=0,
    )
    if updated == 0:
        # No active session — nothing to close (idempotent)
        pass


def _free_station(user_id: int) -> None:
    """Release any station occupied by +user_id+."""
    StationMap.objects.filter(station_user_id=user_id).update(
        station_user_id=None,
    )


def _blacklist_token(raw_token: str) -> None:
    """Blacklist a refresh token so it cannot be reused."""
    try:
        token = RefreshToken(raw_token)
        token.blacklist()
    except Exception:
        # Token already blacklisted or invalid — safe to ignore on logout
        pass


# ---------------------------------------------------------------------------
# Profile / Status
# ---------------------------------------------------------------------------

def get_profile(daily_user: DailyUser) -> dict[str, Any]:
    """Return the user's profile data including active session info."""
    try:
        user_name = daily_user.profile.user_name
    except Exception:
        user_name = f"User #{daily_user.pk}"

    active_session = (
        Session.objects
        .filter(user_id=daily_user.pk, sesion_active=1)
        .select_related("station")
        .first()
    )

    profile: dict[str, Any] = {
        "id": daily_user.pk,
        "name": user_name,
        "role": daily_user.role.name,
        "role_id": daily_user.role.pk,
    }

    if active_session:
        profile["session"] = {
            "id": active_session.pk,
            "station_id": active_session.station_id,
            "station_number": active_session.station.station_number,
            "sesion_in": active_session.sesion_in,
            "status": active_session.sesion_status,
        }
    else:
        profile["session"] = None

    return profile


def update_status(daily_user: DailyUser, new_status: int) -> None:
    """
    Update the status on the user's active session.

    Status values: 0=offline, 1=active, 2=available-for-cover
    """
    updated = Session.objects.filter(
        user_id=daily_user.pk,
        sesion_active=1,
    ).update(sesion_status=new_status)

    if updated == 0:
        raise ResourceNotFound("No hay sesión activa para actualizar el status.")


# ---------------------------------------------------------------------------
# Available Stations
# ---------------------------------------------------------------------------

def get_available_stations() -> list[dict[str, Any]]:
    """Return stations that are not currently occupied by any user."""
    available = (
        StationMap.objects
        .filter(station_user__isnull=True)
        .select_related("station")
        .order_by("station__station_number")
    )

    return [
        {
            "id": mapping.station_id,
            "station_number": mapping.station.station_number,
        }
        for mapping in available
    ]
