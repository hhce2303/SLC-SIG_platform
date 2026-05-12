import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SigProject",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "data",
                    models.JSONField(
                        default=dict,
                        help_text='Canvas payload: {"sitios": [], "devices": [], "enlaces": [], "drawings": []}',
                    ),
                ),
                ("version", models.IntegerField(default=1)),
                ("owner_id", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "sig_projects",
                "ordering": ["-updated_at"],
            },
        ),
    ]
