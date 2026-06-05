import apps.installations.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0006_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteIndoorMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("label", models.CharField(blank=True, default="", max_length=255)),
                ("image", models.FileField(upload_to=apps.installations.models.indoor_map_upload_to)),
                ("content_type", models.CharField(blank=True, default="", max_length=100)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("uploaded_by", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "site_indoor_maps",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="siteindoormap",
            index=models.Index(fields=["site_id", "created_at"], name="indoor_map_site_idx"),
        ),
    ]
