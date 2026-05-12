from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import Special


class SpecialResponseSerializer(serializers.ModelSerializer):
    """
    Read serializer — matches frontend contract for supervisor specials.

    spec_datetime is stored in MySQL as DATETIME without timezone info.
    Its value already represents the site's local time (offset applied at
    creation). We serialize it as a naive ISO string (no Z / no +00:00)
    so the frontend does NOT apply a second UTC→local conversion.

    The field ``site_timezone`` is included so the frontend can label the
    datetime correctly (e.g. display "CST", "MST", etc.).
    """

    # Naive ISO 8601 — no timezone suffix. Value is already site-local time.
    spec_datetime = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S")

    site_name = serializers.CharField(source="site.site_name", read_only=True, default=None)
    site_timezone = serializers.CharField(source="site.site_timezone", read_only=True, default=None)
    act_name = serializers.CharField(source="activity.act_name", read_only=True, default=None)
    operator_name = serializers.CharField(source="user.profile.user_name", read_only=True, default=None)

    class Meta:
        model = Special
        fields = (
            "id",
            "spec_datetime",
            "site_id",
            "site_name",
            "site_timezone",
            "act_name",
            "spec_quantity",
            "spec_camera",
            "spec_description",
            "operator_name",
            "spec_status",
            "spec_marked_by",
            "spec_marked_at",
        )


class MarkSpecialSerializer(serializers.Serializer):
    """Write serializer for mark/unmark. Send status=null to unmark."""

    status = serializers.ChoiceField(
        choices=["done", "flagged"],
        allow_null=True,
    )
