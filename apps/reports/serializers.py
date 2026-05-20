from rest_framework import serializers


class PoliceDispatchReadSerializer(serializers.Serializer):
    id          = serializers.IntegerField()
    datetime    = serializers.DateTimeField()
    siteId      = serializers.IntegerField()
    quantity    = serializers.CharField(allow_null=True)
    camera      = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    userId      = serializers.IntegerField()
    status      = serializers.CharField()
