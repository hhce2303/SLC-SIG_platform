"""
Authentication & session management services.

Ports the following functions from proyecto_app:
  - authenticate_user()  → login()
  - new_sesion_entry()   → _create_session()
  - do_logout()          → logout()
  - free_station()       → _free_station()

Auth model (post ADR-0001, docs/arc42/daily/decisions/0001-...): tokens are
issued directly against daily_users via apps.core.models.User -- no
django.contrib.auth.authenticate()/backend is involved anymore.
authenticate_daily_credentials()/issue_daily_access_token() are shared with
apps.platform.services.platform_login(), which needs the exact same
credential check + token-issuance shape for its station-less login.
"""

from __future__ import annotations

from hmac import compare_digest
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User as AuthUser
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    ConflictError,
    ResourceNotFound,
    ServiceException,
)
from apps.core.models import StationMap, User as DailyUser
from apps.users.authentication import DailyAccessToken
from apps.users.models import Session


# ---------------------------------------------------------------------------
# Shared credential/token helpers (also used by apps.platform.services)
# ---------------------------------------------------------------------------

def authenticate_daily_credentials(user_id: int, password: str) -> DailyUser:
    """
    Validate a (user_id, password) pair directly against daily_users
    (plain-text comparison -- legacy DB, passwords are NOT hashed;
    compare_digest instead of `!=` costs nothing and removes a trivial
    timing side-channel).

    Compatibility shim for apps.schedules (decision logged in ADR-0001 /
    docs/arc42/daily/11_risks_and_technical_debt.md #3): DailyUserBackend
    used to be the only code that ever created a django.contrib.auth.User
    mirror row for an operator. Now that it's deleted, this is the only
    remaining place that happens -- lazily, on first successful login, not
    on account creation (this platform has no operator-onboarding flow of
    its own; operators are loaded directly into daily_users outside
    Django). apps.schedules' soft FKs to auth.User keep resolving as a
    result. Remove once apps.schedules migrates onto apps.core.models.User
    directly.

    Raises:
        ServiceException -- invalid credentials or user not found
    """
    try:
        daily_user = DailyUser.objects.select_related("role").get(pk=user_id)
    except DailyUser.DoesNotExist:
        raise ServiceException("Credenciales inválidas.")

    if not compare_digest(daily_user.password, password):
        raise ServiceException("Credenciales inválidas.")

    AuthUser.objects.get_or_create(
        pk=daily_user.pk,
        defaults={"username": f"daily_{daily_user.pk}", "is_active": True},
    )

    return daily_user


def issue_daily_access_token(daily_user: DailyUser, **extra_claims: Any) -> DailyAccessToken:
    """Build a DailyAccessToken for `daily_user`. No refresh token, ever."""
    token = DailyAccessToken()
    token.set_exp(lifetime=settings.DAILY_JWT["ACCESS_TOKEN_LIFETIME"])
    token["daily_user_id"] = daily_user.pk
    token["role"] = daily_user.role.name
    for claim, value in extra_claims.items():
        token[claim] = value
    return token


def _user_name(daily_user: DailyUser) -> str:
    try:
        return daily_user.profile.user_name
    except Exception:
        return f"User #{daily_user.pk}"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(username: str, password: str, station_id: int) -> dict[str, Any]:
    """
    Authenticate user by name, claim station, create BD session, return JWT.

    Raises:
        ServiceException – invalid credentials or user not found
        ConflictError    – station already occupied or user already logged in
    """
    from apps.core.models import UserName

    try:
        profile = UserName.objects.get(user_name__iexact=username)
        user_id = profile.user_id
    except UserName.DoesNotExist:
        raise ServiceException("Credenciales inválidas.")

    daily_user = authenticate_daily_credentials(user_id, password)

    with transaction.atomic():
        if Session.objects.filter(user_id=daily_user.pk, sesion_active=1).exists():
            raise ConflictError("El usuario ya tiene una sesión activa.")

        _claim_station(daily_user.pk, station_id)
        session = _create_session(daily_user.pk, station_id)

    token = issue_daily_access_token(daily_user)

    return {
        "access": str(token),
        "refresh": None,
        "user": {
            "id": daily_user.pk,
            "name": _user_name(daily_user),
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

def logout(daily_user: DailyUser) -> None:
    """
    Close active BD session and free the station.

    Post-ADR-0001: there is no refresh token to blacklist -- the access
    token remains valid until its natural (~10 year) expiry regardless of
    logout. This is shift/session bookkeeping only, not a revocation
    mechanism (see apps.platform.models.DailyTokenEpoch for that).
    """
    with transaction.atomic():
        _close_session(daily_user.pk)
        _free_station(daily_user.pk)


def _close_session(user_id: int) -> None:
    """Set sesion_out and sesion_active=0 on the current active session."""
    Session.objects.filter(
        user_id=user_id,
        sesion_active=1,
    ).update(
        sesion_out=timezone.now(),
        sesion_active=0,
    )


def _free_station(user_id: int) -> None:
    """Release any station occupied by +user_id+."""
    StationMap.objects.filter(station_user_id=user_id).update(
        station_user_id=None,
    )


# ---------------------------------------------------------------------------
# Profile / Status
# ---------------------------------------------------------------------------

def get_profile(daily_user: DailyUser) -> dict[str, Any]:
    """Return the user's profile data including active session info."""
    active_session = (
        Session.objects
        .filter(user_id=daily_user.pk, sesion_active=1)
        .select_related("station")
        .first()
    )

    profile: dict[str, Any] = {
        "id": daily_user.pk,
        "name": _user_name(daily_user),
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
