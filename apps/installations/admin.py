"""
Installations admin — registered on InstallationsAdminSite.

Models:
  SigProject           — managed=True, default DB (sig_dailylogs).
  PersonalAccessToken  — managed=False, sigtools DB (sigtools_beta).

Actions on PersonalAccessToken:
  revoke_tokens     — fuerza logout de los usuarios seleccionados (borra tokens).
  prune_expired     — elimina todos los tokens ya expirados del sistema.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import format_html

from apps.installations.models import SigProject
from apps.sigtools_auth.models import PersonalAccessToken
from config.admin_sites import installations_admin


# ---------------------------------------------------------------------------
# SigProject
# ---------------------------------------------------------------------------

@admin.register(SigProject, site=installations_admin)
class SigProjectAdmin(ModelAdmin):
    list_display = ("id", "name", "version", "owner_id", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("-updated_at",)
    list_per_page = 50
    readonly_fields = ("id", "created_at", "updated_at")

    def get_fields(self, request: HttpRequest, obj: Any = None):
        return ["id", "name", "version", "owner_id", "data", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# PersonalAccessToken — token management with admin actions
# ---------------------------------------------------------------------------

@admin.register(PersonalAccessToken, site=installations_admin)
class PersonalAccessTokenAdmin(ModelAdmin):
    list_display = (
        "id",
        "tokenable_id",
        "name",
        "token_preview",
        "status_badge",
        "last_used_at",
        "expires_at",
        "created_at",
    )
    search_fields = ("tokenable_id", "name")
    list_filter = ("name",)
    ordering = ("-created_at",)
    list_per_page = 50

    # All fields read-only — tokens must only be manipulated via actions
    def get_readonly_fields(self, request: HttpRequest, obj: Any = None):
        return [f.name for f in PersonalAccessToken._meta.get_fields() if hasattr(f, "name")]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    # ---------------------------------------------------------------------------
    # Display helpers
    # ---------------------------------------------------------------------------

    @admin.display(description="Token (preview)")
    def token_preview(self, obj: PersonalAccessToken) -> str:
        """Show first 8 chars of the SHA-256 hash — enough to identify without exposing it."""
        return f"{obj.token[:8]}…"

    @admin.display(description="Estado")
    def status_badge(self, obj: PersonalAccessToken) -> str:
        now = timezone.now()
        if obj.expires_at is None:
            color, label = "#888", "Sin exp."
        elif obj.expires_at < now:
            color, label = "#dc3545", "Expirado"
        else:
            color, label = "#28a745", "Activo"
        return format_html(
            '<span style="color:{};font-weight:700">{}</span>',
            color,
            label,
        )

    # ---------------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------------

    @admin.action(description="🔐 Revocar tokens seleccionados (forzar logout)")
    def revoke_tokens(self, request: HttpRequest, queryset: QuerySet) -> None:
        """
        Deletes the selected PAT rows from sigtools_beta.
        The affected users will be logged out immediately on their next request.
        """
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f"{count} token(s) revocado(s). "
            "Los usuarios deberán iniciar sesión nuevamente.",
        )

    @admin.action(description="🧹 Limpiar tokens expirados del sistema")
    def prune_expired(self, request: HttpRequest, queryset: QuerySet) -> None:
        """
        Ignores the current selection and deletes ALL expired tokens in the DB.
        Equivalent to running: python manage.py prune_expired_tokens
        """
        deleted, _ = (
            PersonalAccessToken.objects
            .using("sigtools")
            .filter(expires_at__lt=timezone.now())
            .delete()
        )
        self.message_user(
            request,
            f"{deleted} token(s) expirado(s) eliminado(s) del sistema.",
        )

    actions = ["revoke_tokens", "prune_expired"]
