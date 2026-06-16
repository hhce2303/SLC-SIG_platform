from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0010_sigproject_presentation_signature"),
    ]

    operations = [
        migrations.AddField(
            model_name="sigproject",
            name="presentation_pricing",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
