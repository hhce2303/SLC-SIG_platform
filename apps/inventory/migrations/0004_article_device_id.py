"""
Add device_id indexed column to inv_articles.

Populated at migration time from existing latest_note entries that
contain a [device:XXX] tag.  From now on, services.create_article and
services.update_article keep this column in sync so catalog serial
lookups can use WHERE device_id != '' instead of LIKE '%[device:%'.
"""
from __future__ import annotations

import re

from django.db import migrations, models


_TAG_RE = re.compile(r"\[device:([^\]]+)\]")


def _populate_device_id(apps, schema_editor):
    Article = apps.get_model("inventory", "Article")
    to_update = []
    for article in Article.objects.exclude(latest_note="").only("id", "latest_note", "device_id"):
        m = _TAG_RE.search(article.latest_note or "")
        if m:
            article.device_id = m.group(1)
            to_update.append(article)
    if to_update:
        Article.objects.bulk_update(to_update, ["device_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_inventory_new_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="device_id",
            field=models.CharField(
                blank=True, default="", db_index=True, max_length=50
            ),
        ),
        migrations.RunPython(_populate_device_id, migrations.RunPython.noop),
    ]
