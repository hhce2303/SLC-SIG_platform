from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0009_sigproject_presentation_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="sigproject",
            name="presentation_signature",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
