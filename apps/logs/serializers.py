from __future__ import annotations

from rest_framework import serializers

from apps.logs.models import DailyEvent


class DailyEventResponseSerializer(serializers.ModelSerializer):
    """Read serializer — matches the frontend contract exactly."""
    site_name = serializers.CharField(source="site.site_name", read_only=True)
    activity_name = serializers.CharField(source="activity.act_name", read_only=True)

    class Meta:
        model = DailyEvent
        fields = (
            "id",
            "site_name",
            "activity_name",
            "event_datetime",
            "event_status",
            "quantity",
            "camera",
            "description",
        )


class CreateEventSerializer(serializers.Serializer):
    """Write serializer — validates input payload, zero logic."""
    site_id = serializers.IntegerField()
    activity_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0, default=0)
    camera = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
