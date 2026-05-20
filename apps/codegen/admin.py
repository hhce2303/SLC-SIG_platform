"""CodeGen admin — review interface for AI-generated code."""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.codegen.models import CodeGenAudit


@admin.register(CodeGenAudit)
class CodeGenAuditAdmin(admin.ModelAdmin):
    list_display  = ("id", "target_app", "short_request", "status_badge", "reviewed_by", "created_at", "deployed_at")
    list_filter   = ("status", "target_app")
    search_fields = ("user_request", "target_app")
    readonly_fields = (
        "user_request", "target_app", "tables_used",
        "schema_context", "claude_prompt",
        "generated_code", "status",
        "reviewed_by", "reviewed_at", "deployed_at", "deploy_error",
        "created_at",
    )
    fieldsets = (
        ("Request", {
            "fields": ("user_request", "target_app", "tables_used"),
        }),
        ("Pipeline", {
            "fields": ("schema_context", "claude_prompt"),
            "classes": ("collapse",),
        }),
        ("Código generado (solo lectura)", {
            "fields": ("generated_code",),
            "classes": ("collapse",),
        }),
        ("Revisión del admin", {
            "fields": ("final_code", "review_notes"),
        }),
        ("Estado", {
            "fields": ("status", "reviewed_by", "reviewed_at", "deployed_at", "deploy_error"),
        }),
    )

    def short_request(self, obj: CodeGenAudit) -> str:
        return obj.user_request[:80] + "…" if len(obj.user_request) > 80 else obj.user_request
    short_request.short_description = "Request"

    def status_badge(self, obj: CodeGenAudit) -> str:
        colors = {
            "pending":  "#f59e0b",
            "approved": "#10b981",
            "modified": "#3b82f6",
            "rejected": "#ef4444",
            "deployed": "#6366f1",
            "failed":   "#dc2626",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Estado"
