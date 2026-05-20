from rest_framework import serializers

class CameraReadSerializer(serializers.Serializer):
    brand = serializers.CharField()
    camera_type = serializers.CharField()
