from __future__ import annotations

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="user_name from daily_users_names")
    password = serializers.CharField(write_only=True)
    station_id = serializers.IntegerField(help_text="ID_station to claim")


class StationOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    station_number = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Refresh token to blacklist",
    )


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField(
        help_text="0=offline, 1=active, 2=available-for-cover",
    )

    def validate_status(self, value: int) -> int:
        if value not in (0, 1, 2):
            raise serializers.ValidationError(
                "Status debe ser 0 (offline), 1 (active) o 2 (available-for-cover)."
            )
        return value


class SessionInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    station_id = serializers.IntegerField()
    station_number = serializers.CharField()
    sesion_in = serializers.DateTimeField()
    status = serializers.IntegerField()


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    role_id = serializers.IntegerField()
    session = SessionInfoSerializer(allow_null=True)


class LoginResponseSerializer(serializers.Serializer):
    """Schema for drf-spectacular documentation."""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserProfileSerializer()
    session_id = serializers.IntegerField()
    station_id = serializers.IntegerField()


class UsernameItemSerializer(serializers.Serializer):
    username = serializers.CharField()
