from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0011_sigproject_presentation_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="sigproject",
            name="presentation_expires_at",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
