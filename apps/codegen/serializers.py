"""Codegen serializers — zero logic, only data shape."""

from __future__ import annotations

from rest_framework import serializers

from apps.codegen.models import CodeGenAudit


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class CodeGenAuditReadSerializer(serializers.ModelSerializer):
    reviewedBy   = serializers.SerializerMethodField()
    generatedCode = serializers.JSONField(source="generated_code")
    finalCode     = serializers.JSONField(source="final_code")
    schemaContext = serializers.JSONField(source="schema_context")
    claudePrompt  = serializers.CharField(source="claude_prompt")
    userRequest   = serializers.CharField(source="user_request")
    targetApp     = serializers.CharField(source="target_app")
    tablesUsed    = serializers.JSONField(source="tables_used")
    reviewNotes   = serializers.CharField(source="review_notes")
    deployError   = serializers.CharField(source="deploy_error")
    createdAt     = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%S")
    reviewedAt    = serializers.DateTimeField(source="reviewed_at", format="%Y-%m-%dT%H:%M:%S", allow_null=True)
    deployedAt    = serializers.DateTimeField(source="deployed_at", format="%Y-%m-%dT%H:%M:%S", allow_null=True)

    class Meta:
        model = CodeGenAudit
        fields = (
            "id",
            "userRequest",
            "targetApp",
            "tablesUsed",
            "schemaContext",
            "claudePrompt",
            "generatedCode",
            "finalCode",
            "status",
            "reviewedBy",
            "reviewNotes",
            "deployError",
            "createdAt",
            "reviewedAt",
            "deployedAt",
        )

    def get_reviewedBy(self, obj: CodeGenAudit) -> str | None:
        return obj.reviewed_by.get_full_name() or obj.reviewed_by.username if obj.reviewed_by else None


class CodeGenAuditListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view — omits large JSON fields."""
    reviewedBy = serializers.SerializerMethodField()
    targetApp  = serializers.CharField(source="target_app")
    userRequest = serializers.CharField(source="user_request")
    createdAt  = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%S")
    deployedAt = serializers.DateTimeField(source="deployed_at", format="%Y-%m-%dT%H:%M:%S", allow_null=True)

    class Meta:
        model = CodeGenAudit
        fields = ("id", "targetApp", "userRequest", "status", "reviewedBy", "createdAt", "deployedAt")

    def get_reviewedBy(self, obj: CodeGenAudit) -> str | None:
        return obj.reviewed_by.username if obj.reviewed_by else None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

class CodeGenGenerateSerializer(serializers.Serializer):
    userRequest = serializers.CharField(source="user_request", max_length=2000)
    targetApp   = serializers.CharField(source="target_app", max_length=100)
    tablesUsed  = serializers.ListField(
        source="tables_used",
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )


class CodeGenReviewSerializer(serializers.Serializer):
    """Used by admin to update final_code and/or review_notes before deploying."""
    finalCode   = serializers.JSONField(source="final_code", required=False)
    reviewNotes = serializers.CharField(source="review_notes", required=False, allow_blank=True)
