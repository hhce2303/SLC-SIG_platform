from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_article_checklist_date_article_checklist_notes_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaterialsRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("requested_by_id", models.BigIntegerField()),
                ("items", models.JSONField(default=list)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("notes", models.TextField(blank=True, default="")),
                ("reviewer_id", models.BigIntegerField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_materials_requests",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="materialsrequest",
            index=models.Index(fields=["site_id", "status"], name="inv_mr_site_status_idx"),
        ),
        migrations.CreateModel(
            name="DailyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("date", models.DateField(db_index=True)),
                ("submitted_by_id", models.BigIntegerField()),
                ("q1",  models.TextField(blank=True, default="")),
                ("q2",  models.TextField(blank=True, default="")),
                ("q3",  models.TextField(blank=True, default="")),
                ("q4",  models.TextField(blank=True, default="")),
                ("q5",  models.TextField(blank=True, default="")),
                ("q6",  models.TextField(blank=True, default="")),
                ("q7",  models.TextField(blank=True, default="")),
                ("q8",  models.TextField(blank=True, default="")),
                ("q9",  models.TextField(blank=True, default="")),
                ("q10", models.TextField(blank=True, default="")),
                ("q11", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "inv_daily_reports",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="dailyreport",
            index=models.Index(fields=["site_id", "date"], name="inv_dr_site_date_idx"),
        ),
        migrations.CreateModel(
            name="CableRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("label", models.CharField(max_length=255)),
                ("from_location", models.CharField(blank=True, default="", max_length=255)),
                ("to_location", models.CharField(blank=True, default="", max_length=255)),
                ("cable_type", models.CharField(blank=True, default="", max_length=100)),
                ("length_ft", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("complete", "Complete")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_cable_runs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ScopeChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("description", models.TextField()),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("requested_by_id", models.BigIntegerField(blank=True, null=True)),
                ("reviewed_by_id", models.BigIntegerField(blank=True, null=True)),
                ("reviewer_notes", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_scope_changes",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="scopechange",
            index=models.Index(fields=["site_id", "status"], name="inv_sc_site_status_idx"),
        ),
        migrations.CreateModel(
            name="EquipmentReturn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True)),
                ("device_id", models.CharField(max_length=50)),
                ("device_name", models.CharField(blank=True, default="", max_length=255)),
                ("reason", models.TextField(blank=True, default="")),
                ("qty_returned", models.IntegerField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("received_by_id", models.BigIntegerField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("received", "Received")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_equipment_returns",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OperationsAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True, unique=True)),
                ("data", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_operations_assignment",
            },
        ),
        migrations.CreateModel(
            name="ElevatorRental",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.BigIntegerField(db_index=True, unique=True)),
                ("lift_required", models.BooleanField(default=False)),
                ("vendor", models.CharField(blank=True, default="", max_length=255)),
                ("rental_start", models.DateField(blank=True, null=True)),
                ("rental_end", models.DateField(blank=True, null=True)),
                ("cost", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inv_elevator_rental",
            },
        ),
    ]
