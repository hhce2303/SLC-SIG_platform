from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("codegen", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE codegen_codegenaudit CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
