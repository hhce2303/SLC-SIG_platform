"""CodeGen API views — thin orchestration layer. All endpoints require is_staff."""

from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.codegen import selectors, services
from apps.codegen.models import CodeGenAudit
from apps.codegen.serializers import (
    CodeGenAuditListSerializer,
    CodeGenAuditReadSerializer,
    CodeGenGenerateSerializer,
    CodeGenReviewSerializer,
)
from django.utils import timezone


class GenerateView(APIView):
    """
    POST /api/v1/codegen/generate/
    Triggers the full pipeline: schema → Claude prompt → Ollama → AuditLog.
    Blocks until Ollama responds (~45-90s with GPU).
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request: Request) -> Response:
        ser = CodeGenGenerateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        audit = services.generate_code(
            user_request=d["user_request"],
            target_app=d["target_app"],
            tables=d.get("tables_used", []),
        )
        return Response(
            CodeGenAuditReadSerializer(audit).data,
            status=status.HTTP_201_CREATED,
        )


class AuditListView(APIView):
    """GET /api/v1/codegen/audits/"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_audits()
        data = CodeGenAuditListSerializer(qs, many=True).data
        return Response({"data": data, "total": len(data)})


class AuditDetailView(APIView):
    """
    GET  /api/v1/codegen/audits/<id>/   — full detail including code
    PATCH /api/v1/codegen/audits/<id>/  — admin updates final_code / review_notes
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request: Request, audit_id: int) -> Response:
        audit = selectors.get_audit_by_id(audit_id)
        return Response(CodeGenAuditReadSerializer(audit).data)

    def patch(self, request: Request, audit_id: int) -> Response:
        audit = selectors.get_audit_by_id(audit_id)
        ser = CodeGenReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        update_fields = []
        if "final_code" in d:
            audit.final_code = d["final_code"]
            update_fields.append("final_code")
        if "review_notes" in d:
            audit.review_notes = d["review_notes"]
            update_fields.append("review_notes")

        if update_fields:
            audit.save(update_fields=update_fields)

        return Response(CodeGenAuditReadSerializer(audit).data)


class AuditApproveView(APIView):
    """
    POST /api/v1/codegen/audits/<id>/approve/
    Writes final_code to disk and restarts the container.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request: Request, audit_id: int) -> Response:
        audit = selectors.get_audit_by_id(audit_id)

        if audit.status == CodeGenAudit.Status.DEPLOYED:
            return Response(
                {"detail": "Este audit ya fue desplegado."},
                status=status.HTTP_409_CONFLICT,
            )
        if audit.status == CodeGenAudit.Status.REJECTED:
            return Response(
                {"detail": "No se puede aprobar un audit rechazado."},
                status=status.HTTP_409_CONFLICT,
            )

        # Mark as modified if admin changed final_code vs original
        if audit.final_code != audit.generated_code:
            audit.status = CodeGenAudit.Status.MODIFIED
        else:
            audit.status = CodeGenAudit.Status.APPROVED
        audit.reviewed_by = request.user
        audit.reviewed_at = timezone.now()
        audit.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        services.deploy_audit(audit, admin_user=request.user)

        return Response(CodeGenAuditReadSerializer(audit).data)


class AuditRejectView(APIView):
    """POST /api/v1/codegen/audits/<id>/reject/"""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request: Request, audit_id: int) -> Response:
        audit = selectors.get_audit_by_id(audit_id)

        if audit.status == CodeGenAudit.Status.DEPLOYED:
            return Response(
                {"detail": "No se puede rechazar un audit ya desplegado."},
                status=status.HTTP_409_CONFLICT,
            )

        notes = request.data.get("reviewNotes", "")
        audit.status = CodeGenAudit.Status.REJECTED
        audit.reviewed_by = request.user
        audit.reviewed_at = timezone.now()
        audit.review_notes = notes
        audit.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

        return Response(CodeGenAuditReadSerializer(audit).data)
