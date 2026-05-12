from django.db import models


class Tool(models.Model):
    """
    Represents a tool/application connected to the central platform.
    Each tool has its own frontend URL and can be toggled active/inactive.
    """

    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Identificador único. Ej: 'daily', 'inventory', 'schedules'.",
    )
    name = models.CharField(max_length=100, help_text="Nombre visible. Ej: 'Daily Log'.")
    description = models.CharField(max_length=255, blank=True)
    frontend_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL base del frontend de esta herramienta.",
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nombre del ícono o clase CSS. Ej: 'fa-calendar'.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0, help_text="Orden de aparición.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_tools"
        ordering = ["order", "name"]
        verbose_name = "Herramienta"
        verbose_name_plural = "Herramientas"

    def __str__(self) -> str:
        return self.name


class UserToolAccess(models.Model):
    """
    Grants a specific platform user access to a specific tool.
    Users not listed here fall back to the default access policy.
    """

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="tool_accesses",
        db_column="user_id",
    )
    tool = models.ForeignKey(
        Tool,
        on_delete=models.CASCADE,
        related_name="user_accesses",
        db_column="tool_id",
    )
    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_user_tool_access"
        unique_together = [("user", "tool")]
        verbose_name = "Acceso de usuario a herramienta"
        verbose_name_plural = "Accesos de usuarios a herramientas"

    def __str__(self) -> str:
        return f"{self.user_id} → {self.tool.name}"
