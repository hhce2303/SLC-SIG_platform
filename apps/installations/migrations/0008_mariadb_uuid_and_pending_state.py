# Generated manually — 2026-06-07
#
# Fixes the UUIDField mismatch introduced by upgrading to Django 5.1 with
# MariaDB 10.7+.  Django 5.1 sets has_native_uuid_field=True for MariaDB 10.7+
# and queries/stores UUIDs in the native UUID format (with hyphens), but the
# existing columns were created as char(32) (hex without hyphens) by the older
# Django.  The RunSQL operations below convert those columns to MariaDB's native
# UUID type so that all lookups work correctly again.
#
# Also includes state-only operations that Django detected as pending:
#   - CreateModel ProjectSite (managed=False — no DB table created)
#   - AlterField Notification.id → BigAutoField
#   - AlterModelTable AppRolePermission → 'role_permissions'
#     (migration 0002 created it as 'app_role_permissions')

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0007_site_indoor_map"),
    ]

    operations = [
        # ── State-only: ProjectSite is managed=False ──────────────────────────
        migrations.CreateModel(
            name="ProjectSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_group_id", models.BigIntegerField()),
                ("it_backup_id", models.BigIntegerField(blank=True, null=True)),
                ("it_responsible_id", models.BigIntegerField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("ip_address", models.CharField(blank=True, default="0.0.0.0", max_length=250, null=True)),
                ("state_code", models.CharField(blank=True, default="FL", max_length=2, null=True)),
                ("country_code", models.CharField(blank=True, default="US", max_length=2, null=True)),
                ("city", models.CharField(blank=True, max_length=255, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("dealership_info", models.TextField(blank=True, null=True)),
                ("map_path", models.TextField(blank=True, null=True)),
                ("lat", models.FloatField(blank=True, null=True)),
                ("lon", models.FloatField(blank=True, db_column="long", null=True)),
                ("circuit_is_https", models.IntegerField(blank=True, default=0, null=True)),
                ("circuit_status", models.IntegerField(blank=True, default=3, null=True)),
                ("site_subdomain", models.CharField(blank=True, max_length=255, null=True)),
                ("site_subdomain_status", models.CharField(default="none", max_length=10)),
                ("monitored", models.BooleanField(default=True)),
                ("maintenance", models.BooleanField(default=True)),
                ("rental", models.BooleanField(default=True)),
                ("installation_date", models.DateField(blank=True, null=True)),
                ("site_status_id", models.BigIntegerField(blank=True, default=1, null=True)),
                ("site_id", models.BigIntegerField(blank=True, null=True)),
                ("cameras_count", models.IntegerField(default=0)),
                ("preowned_cameras_count", models.IntegerField(default=0)),
                ("exterior_cameras_count", models.IntegerField(default=0)),
                ("teams_channelid", models.CharField(blank=True, default="", max_length=255)),
                ("teams_teamid", models.CharField(blank=True, default="", max_length=255)),
                ("timezone", models.CharField(blank=True, default="America/New_York", max_length=50, null=True)),
                ("verification_status", models.CharField(default="pending", max_length=20)),
                ("created_by", models.BigIntegerField(blank=True, null=True)),
                ("approval_requested_by", models.BigIntegerField(blank=True, null=True)),
                ("verified_by", models.BigIntegerField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("authorized_by", models.BigIntegerField(blank=True, null=True)),
                ("authorized_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "project_sites",
                "managed": False,
            },
        ),

        # ── State update: Notification.id AutoField → BigAutoField ────────────
        migrations.AlterField(
            model_name="notification",
            name="id",
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
        ),

        # ── DB change: rename AppRolePermission table ─────────────────────────
        # Migration 0002 created it as 'app_role_permissions'; model now uses 'role_permissions'.
        migrations.AlterModelTable(
            name="approlepermission",
            table="role_permissions",
        ),

        # ── DB change: convert UUID columns to MariaDB native UUID type ───────
        # Django 5.1 + MariaDB 10.7+ uses has_native_uuid_field=True, so it
        # queries UUIDs with hyphens.  The old char(32) data is stored as hex
        # without hyphens.  ALTER TABLE converts the data automatically.
        migrations.RunSQL(
            sql=[
                "ALTER TABLE sig_projects MODIFY id uuid NOT NULL",
                "ALTER TABLE notifications MODIFY related_project_id uuid NULL",
            ],
            reverse_sql=[
                # Reverse: convert back to char(32) hex (data will lose hyphens)
                "ALTER TABLE sig_projects MODIFY id char(32) NOT NULL",
                "ALTER TABLE notifications MODIFY related_project_id char(32) NULL",
            ],
        ),
    ]
