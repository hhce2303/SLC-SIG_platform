"""CodeGen audit models — tracks every AI code generation request."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class CodeGenAudit(models.Model):
    class Status(models.TextChoices):
        PENDING  = "pending",  "Pendiente de revisión"
        APPROVED = "approved", "Aprobado"
        MODIFIED = "modified", "Aprobado con cambios"
        REJECTED = "rejected", "Rechazado"
        DEPLOYED = "deployed", "Desplegado"
        FAILED   = "failed",   "Error en despliegue"

    # ── Input ──────────────────────────────────────────────────────────────
    user_request   = models.TextField(help_text="Descripción en lenguaje natural del endpoint a generar")
    target_app     = models.CharField(max_length=100, help_text="Nombre del app Django destino (ej: cameras)")
    tables_used    = models.JSONField(default=list, help_text="Tablas del schema usadas como contexto")

    # ── Pipeline ───────────────────────────────────────────────────────────
    schema_context = models.JSONField(default=dict, help_text="Schema de tablas extraído via SQLAlchemy")
    claude_prompt  = models.TextField(blank=True, help_text="Prompt estructurado que Claude generó para el modelo local")

    # ── Output ─────────────────────────────────────────────────────────────
    generated_code = models.JSONField(default=dict, help_text='{"views.py": "...", "serializers.py": "..."}')
    final_code     = models.JSONField(default=dict, help_text="Código tras revisión/modificación del admin")

    # ── Review ─────────────────────────────────────────────────────────────
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_by  = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_generations",
    )
    review_notes = models.TextField(blank=True)

    # ── Meta ───────────────────────────────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    deployed_at  = models.DateTimeField(null=True, blank=True)
    deploy_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.status}] {self.target_app} — {self.created_at:%Y-%m-%d %H:%M}"
