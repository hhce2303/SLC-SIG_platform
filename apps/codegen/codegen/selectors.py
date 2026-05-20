"""Read-only queries for codegen audit log."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.codegen.models import CodeGenAudit


def get_all_audits() -> QuerySet[CodeGenAudit]:
    return CodeGenAudit.objects.select_related("reviewed_by").all()


def get_audit_by_id(audit_id: int) -> CodeGenAudit:
    return CodeGenAudit.objects.select_related("reviewed_by").get(pk=audit_id)


def get_pending_audits() -> QuerySet[CodeGenAudit]:
    return (
        CodeGenAudit.objects
        .filter(status=CodeGenAudit.Status.PENDING)
        .select_related("reviewed_by")
    )
