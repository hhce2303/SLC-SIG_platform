from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0002_apppermission_approle_approlepermission_userapprole_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItSiteTest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True, unique=True)),
                ("references", models.JSONField(default=list)),
                ("camera_flags", models.JSONField(default=list)),
                ("checklist", models.JSONField(default=list)),
                ("grade", models.CharField(blank=True, default="", max_length=20)),
                ("summary", models.TextField(blank=True, default="")),
                ("delays", models.JSONField(default=list)),
                ("attachments", models.JSONField(default=list)),
                ("date", models.DateField(blank=True, null=True)),
                ("start_time", models.TimeField(blank=True, null=True)),
                ("end_time", models.TimeField(blank=True, null=True)),
                ("technicians", models.JSONField(default=list)),
                ("it_personnel", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "it_site_tests",
            },
        ),
        migrations.CreateModel(
            name="SiteProjectInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True, unique=True)),
                ("check_in", models.DateField(blank=True, null=True)),
                ("check_out", models.DateField(blank=True, null=True)),
                ("paylocity_code", models.CharField(blank=True, default="", max_length=50)),
                ("extra_notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "site_project_info",
            },
        ),
    ]
