from rest_framework import serializers


class LayerSerializer(serializers.Serializer):
    """Serializer para layers de sigtools."""
    id = serializers.IntegerField()
    name = serializers.CharField()
