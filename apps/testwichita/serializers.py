from rest_framework import serializers


class CameraSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    serial = serializers.CharField()
    brand = serializers.CharField()
    model = serializers.CharField()
    camera_type = serializers.CharField()
    ip_address = serializers.CharField()
    status = serializers.IntegerField()
