from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0008_mariadb_uuid_and_pending_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="sigproject",
            name="presentation_token",
            field=models.UUIDField(blank=True, default=None, null=True),
        ),
        migrations.AddIndex(
            model_name="sigproject",
            index=models.Index(fields=["presentation_token"], name="sig_projects_pres_tok_idx"),
        ),
    ]
