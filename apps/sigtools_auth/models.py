"""
Unmanaged models for sigtools_auth.
Routes to 'sigtools' DB via the existing SigtoolsRouter (app_label="sigtools").
"""
from django.db import models


class PersonalAccessToken(models.Model):
    """
    Maps to sigtools_beta.personal_access_tokens (created by Laravel Sanctum).
    managed=False — Django never creates or alters this table.

    The `token` column stores SHA-256(plaintext), NOT the plaintext itself.
    The plaintext is never persisted.
    """
    id = models.BigAutoField(primary_key=True)
    tokenable_type = models.CharField(max_length=255)   # "App\\Models\\User"
    tokenable_id = models.BigIntegerField()              # FK to sigtools_beta.users.id
    name = models.CharField(max_length=255)
    token = models.CharField(max_length=64, unique=True) # sha256 hex (64 chars)
    abilities = models.TextField(null=True, blank=True)  # JSON string, e.g. '["*"]'
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        app_label = "sigtools"   # routed to sigtools_beta by SigtoolsRouter
        db_table = "personal_access_tokens"

    def __str__(self) -> str:
        return f"PAT #{self.id} (user {self.tokenable_id})"
