from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0005_sigproject_approval_audit_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recipient_id", models.BigIntegerField(db_index=True)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("approval_request", "Approval Request"),
                            ("approval_approved", "Approval Approved"),
                            ("approval_rejected", "Approval Rejected"),
                            ("onboarding", "Onboarding"),
                            ("inventory_dispatch", "Inventory Dispatch"),
                            ("system", "System"),
                        ],
                        default="system",
                        max_length=30,
                    ),
                ),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("related_project_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "notifications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient_id", "is_read"], name="notif_recipient_unread_idx"),
        ),
    ]
