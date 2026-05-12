from __future__ import annotations

from django.db import models


class ArticleStatus(models.TextChoices):
    ACTIVO = "activo", "Activo"
    REPARADO = "reparado", "Reparado"
    REPARACION = "reparacion", "En reparación"
    DANADO = "danado", "Dañado"


class ArticleCategory(models.TextChoices):
    PERIFERICOS = "Perifericos", "Periféricos"
    ELECTRODOMESTICOS = "Electrodomesticos", "Electrodomésticos"
    MOBILIARIO = "Mobiliario", "Mobiliario"
    COMPUTADORES = "Computadores", "Computadores"
    PARTES_ELECTRONICAS = "Partes Electronicas", "Partes Electrónicas"


class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    icon_name = models.CharField(max_length=50, blank=True, default="Package")
    color = models.CharField(max_length=30, blank=True, default="#6366f1")

    class Meta:
        db_table = "inv_groups"

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    sku = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    sub = models.CharField(max_length=200, blank=True, default="")
    category = models.CharField(max_length=50, choices=ArticleCategory.choices)
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.ACTIVO,
    )
    location = models.CharField(max_length=200, blank=True, default="")
    acquisition_date = models.DateField(null=True, blank=True)
    image = models.CharField(max_length=500, blank=True, default="")
    serial = models.CharField(max_length=200, blank=True, default="")
    modified_by = models.CharField(max_length=100, blank=True, default="")
    latest_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_articles"

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class ActivityLog(models.Model):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "inv_activity_logs"
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.action} on Article #{self.article_id}"
