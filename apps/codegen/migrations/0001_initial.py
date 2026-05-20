from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="CodeGenAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_request", models.TextField(help_text="Descripción en lenguaje natural del endpoint a generar")),
                ("target_app", models.CharField(max_length=100, help_text="Nombre del app Django destino (ej: cameras)")),
                ("tables_used", models.JSONField(default=list, help_text="Tablas del schema usadas como contexto")),
                ("schema_context", models.JSONField(default=dict, help_text="Schema de tablas extraído via SQLAlchemy")),
                ("claude_prompt", models.TextField(blank=True, help_text="Prompt estructurado que Claude generó para el modelo local")),
                ("generated_code", models.JSONField(default=dict, help_text='{"views.py": "...", "serializers.py": "..."}')),
                ("final_code", models.JSONField(default=dict, help_text="Código tras revisión/modificación del admin")),
                ("status", models.CharField(
                    choices=[
                        ("pending",  "Pendiente de revisión"),
                        ("approved", "Aprobado"),
                        ("modified", "Aprobado con cambios"),
                        ("rejected", "Rechazado"),
                        ("deployed", "Desplegado"),
                        ("failed",   "Error en despliegue"),
                    ],
                    default="pending",
                    max_length=20,
                    db_index=True,
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_generations",
                    to="auth.user",
                )),
                ("review_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("deployed_at", models.DateTimeField(blank=True, null=True)),
                ("deploy_error", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="codegenaudit",
            index=models.Index(fields=["status", "-created_at"], name="codegen_status_created_idx"),
        ),
    ]
