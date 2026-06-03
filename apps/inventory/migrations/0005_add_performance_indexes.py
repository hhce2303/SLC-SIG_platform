"""Add performance indexes to inventory models — idempotent via RunPython."""

from django.db import migrations, models


def _index_exists(cursor, table, index_name):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        [table, index_name],
    )
    return cursor.fetchone()[0] > 0


def _table_exists(cursor, table):
    cursor.execute("SHOW TABLES LIKE %s", [table])
    return cursor.fetchone() is not None


INDEXES = [
    ("inventory_article",        "inv_articles_status_idx",       "CREATE INDEX inv_articles_status_idx ON inventory_article (status)"),
    ("inventory_article",        "inv_articles_updated_at_idx",   "CREATE INDEX inv_articles_updated_at_idx ON inventory_article (updated_at)"),
    ("inventory_article",        "inv_art_status_updated_idx",    "CREATE INDEX inv_art_status_updated_idx ON inventory_article (status, updated_at)"),
    ("inventory_activitylog",    "inv_actlog_timestamp_idx",      "CREATE INDEX inv_actlog_timestamp_idx ON inventory_activitylog (timestamp)"),
    ("inventory_materialsrequest","inv_matreq_created_at_idx",    "CREATE INDEX inv_matreq_created_at_idx ON inventory_materialsrequest (created_at)"),
    ("inventory_materialsrequest","inv_matreq_updated_at_idx",    "CREATE INDEX inv_matreq_updated_at_idx ON inventory_materialsrequest (updated_at)"),
    ("inventory_dailyreport",    "inv_dailyrep_created_at_idx",   "CREATE INDEX inv_dailyrep_created_at_idx ON inventory_dailyreport (created_at)"),
]


def add_indexes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table, index_name, sql in INDEXES:
            if _table_exists(cursor, table) and not _index_exists(cursor, table, index_name):
                cursor.execute(sql)


def remove_indexes(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table, index_name, _ in INDEXES:
            if _table_exists(cursor, table) and _index_exists(cursor, table, index_name):
                cursor.execute(f"DROP INDEX {index_name} ON {table}")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_article_device_id"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_indexes, remove_indexes),
            ],
            state_operations=[
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
                migrations.AddIndex(
                    model_name="activitylog",
                    index=models.Index(fields=["timestamp"], name="inv_actlog_timestamp_idx"),
                ),
                migrations.AddIndex(
                    model_name="materialsrequest",
                    index=models.Index(fields=["created_at"], name="inv_matreq_created_at_idx"),
                ),
                migrations.AddIndex(
                    model_name="materialsrequest",
                    index=models.Index(fields=["updated_at"], name="inv_matreq_updated_at_idx"),
                ),
                migrations.AddIndex(
                    model_name="dailyreport",
                    index=models.Index(fields=["created_at"], name="inv_dailyrep_created_at_idx"),
                ),
            ],
        ),
    ]
