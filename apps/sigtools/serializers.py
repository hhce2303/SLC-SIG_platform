"""Sigtools serializers — zero logic, only data shape."""

from __future__ import annotations

from rest_framework import serializers


class SiteSerializer(serializers.Serializer):
    """Serializer para sitios."""

    id             = serializers.IntegerField()
    name           = serializers.CharField()
    cameras_count  = serializers.IntegerField(allow_null=True)
