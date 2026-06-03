"""
Serializers for the web cookie auth system.
Input validation only — no business logic.
"""
from rest_framework import serializers


class WebLoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=255,
        help_text="AD username without @sig.com domain suffix.",
    )
    password = serializers.CharField(write_only=True, max_length=255)


class SigtoolsUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    username = serializers.CharField(allow_null=True)
    roles = serializers.ListField(child=serializers.CharField(), default=list)
    permissions = serializers.ListField(child=serializers.CharField(), default=list)


class WebLoginResponseSerializer(serializers.Serializer):
    user = SigtoolsUserSerializer()
    access_level = serializers.IntegerField()
    access_token = serializers.CharField(
        help_text="Sanctum token in '{id}|{plaintext}' format. "
                  "Send as 'Authorization: Bearer <token>' for cross-origin clients. "
                  "Also set as an HttpOnly cookie (sig_token) for same-origin browser use."
    )
