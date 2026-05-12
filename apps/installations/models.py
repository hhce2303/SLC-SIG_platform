"""
Installations models.

SigProject — managed=True, lives in the default DB (sig_dailylogs).
             Django handles its migration.

Unmanaged sigtools_beta models (managed=False) are defined in
apps/sigtools/models.py — no need to duplicate them here.
"""
from __future__ import annotations

import uuid

from django.db import models


class SigProject(models.Model):
    """
    Canvas design project — stores map layout JSON.
    owner_id references the bigint PK of sigtools_beta.users (cross-DB,
    so no FK constraint — stored as plain IntegerField).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    data = models.JSONField(
        default=dict,
        help_text='Canvas payload: {"sitios": [], "devices": [], "enlaces": [], "drawings": []}',
    )
    version = models.IntegerField(default=1)
    owner_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "sig_projects"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name
