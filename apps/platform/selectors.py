from __future__ import annotations

from apps.core.models import StationInfo, StationMap


def get_station_by_number(station_number: str) -> StationInfo | None:
    return (
        StationInfo.objects
        .only("id", "station_number")
        .filter(station_number__iexact=station_number)
        .first()
    )


def get_station_mapping(station_id: int) -> StationMap | None:
    return (
        StationMap.objects
        .only("station_id", "station_user_id", "is_active")
        .filter(station_id=station_id)
        .first()
    )