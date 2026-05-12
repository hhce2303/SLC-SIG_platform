from rest_framework import serializers


class PlatformLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)


class StationConfigQuerySerializer(serializers.Serializer):
    station_number = serializers.CharField(max_length=20)

    def validate_station_number(self, value: str) -> str:
        normalized_value = value.strip().upper()
        if not normalized_value:
            raise serializers.ValidationError("station_number es requerido.")
        return normalized_value


class StationConfigSerializer(serializers.Serializer):
    station_id = serializers.IntegerField()
    station_number = serializers.CharField()
    occupied = serializers.BooleanField()
    is_active = serializers.BooleanField(allow_null=True)


class ToolSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    frontend_url = serializers.CharField()
    icon = serializers.CharField()


class PlatformUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    role_id = serializers.IntegerField()


class PlatformLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = PlatformUserSerializer()
    tools = ToolSerializer(many=True)
