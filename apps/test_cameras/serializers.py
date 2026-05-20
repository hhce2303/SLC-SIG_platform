"""Test Cameras serializers — zero logic, only data shape."""

from __future__ import annotations

from rest_framework import serializers


class CameraSerializer(serializers.Serializer):
    """Camera detail from sigtools DB."""
    
    id = serializers.IntegerField()
    serial = serializers.CharField()
    brand = serializers.CharField()
    model = serializers.CharField()
    camera_type = serializers.CharField()
    ip_address = serializers.CharField()
    status = serializers.IntegerField()
