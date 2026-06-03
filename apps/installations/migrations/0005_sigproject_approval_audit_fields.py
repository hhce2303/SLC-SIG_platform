from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0004_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="sigproject",
            name="approval_requested_by",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sigproject",
            name="approval_status",
            field=models.CharField(default="draft", max_length=30),
        ),
        migrations.AddField(
            model_name="sigproject",
            name="created_by",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
