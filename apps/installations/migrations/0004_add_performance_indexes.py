"""Add performance indexes to installations models."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0003_itsitetest_siteprojectinfo"),
    ]

    operations = [
        # SigProject: updated_at (ordering + SSE polling)
        migrations.AddIndex(
            model_name="sigproject",
            index=models.Index(fields=["updated_at"], name="sig_projects_updated_at_idx"),
        ),
        # SiteDeviceDispatch: updated_at (SSE polling)
        migrations.AddIndex(
            model_name="sitedevicedispatch",
            index=models.Index(fields=["updated_at"], name="site_dispatch_updated_at_idx"),
        ),
        # SiteDeviceLog: created_at (ordering + SSE polling)
        migrations.AddIndex(
            model_name="sitedevicelog",
            index=models.Index(fields=["created_at"], name="site_devlog_created_at_idx"),
        ),
    ]
