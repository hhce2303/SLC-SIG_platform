from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.core.models import UserRole, UserName, Site, Activity, StationInfo


class UserRoleSerializer(ModelSerializer):
    class Meta:
        model = UserRole
        fields = ("id", "name")


class UserNameSerializer(ModelSerializer):
    class Meta:
        model = UserName
        fields = ("user_id", "user_name")


class SiteSerializer(ModelSerializer):
    class Meta:
        model = Site
        fields = ("id", "group_id", "site_name", "site_dns", "site_timezone")


class ActivitySerializer(ModelSerializer):
    class Meta:
        model = Activity
        fields = ("id", "act_name")


class StationInfoSerializer(ModelSerializer):
    class Meta:
        model = StationInfo
        fields = ("id", "station_number")


# ---------------------------------------------------------------------------
# Catalog response serializers (read-only, for drf-spectacular)
# ---------------------------------------------------------------------------

class SiteCatalogSerializer(ModelSerializer):
    """Sites with ID concatenated to name — used by catalog endpoint."""
    site_name = serializers.CharField(
        help_text="Formato: 'ID - site_name'",
    )

    class Meta:
        model = Site
        fields = ("id", "site_name")


class ActivityCatalogSerializer(ModelSerializer):
    class Meta:
        model = Activity
        fields = ("id", "act_name")
