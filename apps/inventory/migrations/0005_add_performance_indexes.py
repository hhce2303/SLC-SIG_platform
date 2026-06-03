"""Add performance indexes to inventory models."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_article_device_id"),
    ]

    operations = [
        # Article: status (usado en get_dashboard_stats + filtros), updated_at (SSE polling)
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["status"], name="inv_articles_status_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["updated_at"], name="inv_articles_updated_at_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["status", "updated_at"], name="inv_art_status_updated_idx"),
        ),
        # ActivityLog: timestamp (ordering)
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["timestamp"], name="inv_actlog_timestamp_idx"),
        ),
        # MaterialsRequest: created_at (ordering), updated_at (SSE polling)
        migrations.AddIndex(
            model_name="materialsrequest",
            index=models.Index(fields=["created_at"], name="inv_matreq_created_at_idx"),
        ),
        migrations.AddIndex(
            model_name="materialsrequest",
            index=models.Index(fields=["updated_at"], name="inv_matreq_updated_at_idx"),
        ),
        # DailyReport: created_at (ordering)
        migrations.AddIndex(
            model_name="dailyreport",
            index=models.Index(fields=["created_at"], name="inv_dailyrep_created_at_idx"),
        ),
    ]
