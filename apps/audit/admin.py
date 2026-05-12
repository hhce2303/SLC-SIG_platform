from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_id",
        "action",
        "resource",
        "resource_id",
        "ip_address",
        "created_at",
    )
    list_filter = ("action", "resource")
    search_fields = ("user_id", "action", "resource", "detail")
    list_per_page = 50
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "user_id",
        "session_id",
        "action",
        "resource",
        "resource_id",
        "detail",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
