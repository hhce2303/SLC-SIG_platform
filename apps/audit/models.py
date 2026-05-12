from django.db import models


class AuditLog(models.Model):
    """New table for centralized API audit logging. managed=True."""

    id = models.BigAutoField(primary_key=True)
    user_id = models.IntegerField(db_index=True)
    session_id = models.IntegerField(null=True, blank=True)
    action = models.CharField(max_length=100)
    resource = models.CharField(max_length=100)
    resource_id = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "daily_audit_log"
        indexes = [
            models.Index(fields=["user_id", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.created_at}] {self.action} by user {self.user_id}"
