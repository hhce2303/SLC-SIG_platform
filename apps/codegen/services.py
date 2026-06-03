"""
CodeGen services — main pipeline:
  1. get_schema_context()   (schema_inspector.py)
  2. build_ollama_prompt()  (Python template — no LLM, conventions embedded in Modelfile)
  3. call_local_model()     (Ollama on dedicated PC via LAN)
  4. parse_generated_code() (extract files from model output)
  5. deploy_audit()         (admin-triggered: write files + restart)
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
import socket
import threading
import time
from pathlib import Path

import httpx
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone

from apps.codegen.models import CodeGenAudit
from apps.codegen.schema_inspector import get_schema_context

logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL    = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.100:11434")
OLLAMA_MODEL       = os.environ.get("OLLAMA_MODEL", "sigtools-coder")
OLLAMA_TIMEOUT     = int(os.environ.get("OLLAMA_TIMEOUT", "300"))   # 5 min for large models
BASE_APPS_DIR      = Path(os.environ.get("BASE_APPS_DIR", "/app/apps"))
BACKUP_DIR         = Path(os.environ.get("CODEGEN_BACKUP_DIR", "/app/codegen_backups"))
DOCKER_CONTAINER   = os.environ.get("DOCKER_CONTAINER_NAME", "SIGplatform-web")

# (Anthropic client removed — code generation runs fully on the local model)
# Project conventions are embedded in the Modelfile system prompt.

# ---------------------------------------------------------------------------
# Legacy constant kept so existing CodeGenAudit.claude_prompt references compile
# ---------------------------------------------------------------------------
FEW_SHOT_EXAMPLES = '''
=== EJEMPLO 1: Endpoint GET — Listado con FK ===

# selectors.py
def get_all_articles() -> QuerySet[Article]:
    return Article.objects.select_related("group").all()

# serializers.py
class ArticleReadSerializer(serializers.ModelSerializer):
    groupId = serializers.IntegerField(source="group_id", allow_null=True)
    lastMod = serializers.DateTimeField(source="updated_at", format="%Y-%m-%dT%H:%M:%S")

    class Meta:
        model = Article
        fields = ("id", "name", "groupId", "status", "lastMod")

class ArticleWriteSerializer(serializers.Serializer):
    name   = serializers.CharField(max_length=200)
    status = serializers.CharField(max_length=20, default="activo")

# views.py
class ArticleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_articles()
        data = ArticleReadSerializer(qs, many=True).data
        return Response({"data": data, "total": len(data)})

    def post(self, request: Request) -> Response:
        ser = ArticleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        article = services.create_article(data=ser.validated_data)
        return Response(ArticleReadSerializer(article).data, status=status.HTTP_201_CREATED)

# urls.py
path("articles/", ArticleListCreateView.as_view(), name="myapp-articles"),

=== EJEMPLO 2: Endpoint GET — Detalle + PATCH + DELETE ===

# selectors.py
def get_article_by_id(article_id: int) -> Article:
    return Article.objects.select_related("group").get(pk=article_id)

# views.py
class ArticleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, article_id: int) -> Response:
        article = selectors.get_article_by_id(article_id)
        return Response(ArticleReadSerializer(article).data)

    def patch(self, request: Request, article_id: int) -> Response:
        ser = ArticleUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        article = services.update_article(article_id, data=ser.validated_data)
        return Response(ArticleReadSerializer(article).data)

    def delete(self, request: Request, article_id: int) -> Response:
        services.delete_article(article_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

# urls.py
path("articles/<int:article_id>/", ArticleDetailView.as_view(), name="myapp-article-detail"),

=== REGLAS OBLIGATORIAS ===
- Solo APIView. Nunca ViewSet, GenericAPIView, ni @api_view.
- Views solo orquestan: llaman selector/service → serializan → Response. Cero lógica.
- Selectors: read-only, siempre select_related/prefetch_related.
- Services: writes con transaction.atomic(). Argumento keyword-only: *, data:.
- camelCase en respuestas API (usar source= en serializer).
- Sin Model.objects.* en views ni serializers.
- Siempre permission_classes = [IsAuthenticated].
- ReadSerializer hereda de ModelSerializer. WriteSerializer hereda de serializers.Serializer.
- Respuesta de listado: {"data": [...], "total": N}
'''

ARCHITECTURE_RULES = """
REGLAS DEL PROYECTO (no negociables):
1. Solo APIView — nunca ViewSet, GenericAPIView, @api_view
2. Views solo orquestan — llaman selector() o service() → serializan → Response
3. Selectors — read-only, siempre select_related/prefetch_related para FKs
4. Services — writes con transaction.atomic(), keyword args: *, data:
5. camelCase en respuestas API usando source= en ReadSerializer
6. Sin Model.objects.* directo en views ni serializers
7. permission_classes = [IsAuthenticated] en todas las views
8. ReadSerializer hereda de ModelSerializer, WriteSerializer de serializers.Serializer
9. Respuesta de listado: {"data": [...], "total": N}
10. urls.py: flat path() list, sin DefaultRouter, sin app_name namespace
"""

# ---------------------------------------------------------------------------
# Step 2: Claude builds the structured prompt for the local model
# ---------------------------------------------------------------------------

def build_ollama_prompt(user_request: str, schema: dict, target_app: str = "myapp") -> str:
    """
    Builds a structured prompt for the local sigtools-coder model.
    Pure Python template — zero LLM calls.
    Project conventions are embedded in the model's Modelfile system prompt;
    here we only inject the runtime-specific schema and the user's request.
    """
    schema_lines: list[str] = []
    for table, info in schema.items():
        col_strs = " | ".join(
            f"{c['name']} {c['type']}" + (" NULL" if c["nullable"] else "")
            for c in info["columns"]
        )
        schema_lines.append(f"Table `{table}`: {col_strs}")
        for fk in info["foreign_keys"]:
            cols = ", ".join(fk["columns"])
            schema_lines.append(f"  FK: {cols} -> {fk['references']}")

    schema_str = "\n".join(schema_lines) if schema_lines else "(schema not provided)"

    return (
        f"TARGET APP: apps.{target_app}\n\n"
        f"RUNTIME SCHEMA (use EXACTLY these column names — never invent columns):\n"
        f"{schema_str}\n\n"
        f"IMPORTS must use:\n"
        f"  from apps.{target_app}.models import ...\n"
        f"  from apps.{target_app} import selectors\n"
        f"  from apps.{target_app} import services  # only if write ops needed\n\n"
        f"REQUIRED FILES — generate ALL of these, even if minimal:\n"
        f"  === models.py ===   (unmanaged Django model — managed=False, use exact DB column names from schema)\n"
        f"  === selectors.py === (read-only queries — use Model.objects.using('sigtools') for sigtools_beta tables,\n"
        f"                        or connections['sigtools'].cursor() for raw SQL; always select_related for FKs)\n"
        f"  === serializers.py === (ReadSerializer extends ModelSerializer with camelCase via source=)\n"
        f"  === views.py ===    (APIView only, permission_classes=[IsAuthenticated], import Request and status)\n"
        f"  === urls.py ===     (flat path() list, no DefaultRouter, no app_name)\n\n"
        f"TASK: {user_request}"
    )


# ---------------------------------------------------------------------------
# Step 3: Call local Ollama model
# ---------------------------------------------------------------------------

def call_local_model(prompt: str) -> dict:
    """
    Sends the structured prompt to Ollama on the dedicated PC (LAN).
    Returns parsed dict of {filename: code}.
    """
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,    # low temp = more predictable code
                    "num_predict": 4096,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()["response"]
        logger.info("Ollama generation complete. Raw length: %d chars", len(raw))
        return parse_generated_code(raw)
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"No se pudo conectar con Ollama en {OLLAMA_BASE_URL}. "
            "Verifica que el PC dedicado esté encendido y Ollama corriendo."
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"Ollama tardó más de {OLLAMA_TIMEOUT}s. "
            "Considera usar un modelo más pequeño o verificar la GPU."
        ) from exc


# ---------------------------------------------------------------------------
# Step 4: Parse model output into {filename: code} dict
# ---------------------------------------------------------------------------

def parse_generated_code(raw: str) -> dict:
    """
    Extracts files from the model output.
    Expects delimiters:  === filename.py ===
    Uses re.split so each file block is captured cleanly with no trailing artifacts.
    """
    files: dict[str, str] = {}
    # Split on separators — capturing group gives alternating [preamble, name, code, name, code, ...]
    parts = re.split(r"(?:^|\n)===[ \t]*([\w.]+\.py)[ \t]*===[ \t]*(?:\n|$)", raw)
    i = 1
    while i + 1 <= len(parts) - 1:
        filename = parts[i].strip()
        code = parts[i + 1]
        # Strip markdown code fences if model wraps output in ```python ... ```
        code = re.sub(r"^```[a-z]*\n?", "", code.strip())
        code = re.sub(r"\n?```\s*$", "", code)
        code = code.strip()
        if filename and code:
            files[filename] = code
        i += 2
    if not files:
        logger.warning("parse_generated_code: no file blocks found. Raw snippet: %s", raw[:500])
    return files


# ---------------------------------------------------------------------------
# Main pipeline — orchestrates steps 1-4, creates audit entry
# ---------------------------------------------------------------------------

def generate_code(*, user_request: str, target_app: str, tables: list[str]) -> CodeGenAudit:
    """
    Full generation pipeline. Returns a CodeGenAudit in PENDING state.
    Blocks until the local model completes (~45-90s with GPU).
    """
    # 1. Schema introspection — use sigtools URL when target is sigtools
    sigtools_url = os.environ.get("SIGTOOLS_SQLALCHEMY_URL")
    use_sigtools = sigtools_url and target_app in ("sigtools", "sites")
    schema = get_schema_context(
        tables if tables else None,
        db_url=sigtools_url if use_sigtools else None,
    )

    # 2. Claude builds the structured prompt
    claude_prompt = build_ollama_prompt(user_request, schema, target_app=target_app)

    # 3. Create audit entry early (has an ID before the slow Ollama call)
    audit = CodeGenAudit.objects.create(
        user_request=user_request,
        target_app=target_app,
        tables_used=tables,
        schema_context=schema,
        claude_prompt=claude_prompt,
        status=CodeGenAudit.Status.PENDING,
    )

    # 4. Call local model (slow step)
    try:
        generated = call_local_model(claude_prompt)
    except RuntimeError as exc:
        audit.status = CodeGenAudit.Status.FAILED
        audit.deploy_error = str(exc)
        close_old_connections()
        audit.save(update_fields=["status", "deploy_error"])
        raise

    # 5. Persist results — reconnect after long Ollama call (MySQL may have dropped the idle connection)
    close_old_connections()
    audit.generated_code = generated
    audit.final_code = dict(generated)   # admin may modify final_code before deploy
    audit.save(update_fields=["generated_code", "final_code"])

    return audit


# ---------------------------------------------------------------------------
# Deploy — admin-triggered after review
# ---------------------------------------------------------------------------

class _UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over UNIX domain socket (Docker Engine API)."""

    def __init__(self, socket_path: str) -> None:
        super().__init__("localhost")
        self._socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._socket_path)


def _restart_container(delay: int = 5) -> None:
    """Restarts the Django container after a delay (runs in background thread)."""
    def _do_restart() -> None:
        time.sleep(delay)
        try:
            conn = _UnixHTTPConnection("/var/run/docker.sock")
            conn.request(
                "POST",
                f"/containers/{DOCKER_CONTAINER}/restart?t=5",
                headers={"Content-Type": "application/json"},
            )
            conn.getresponse()
        except Exception as exc:
            logger.error("Container restart failed: %s", exc)

    threading.Thread(target=_do_restart, daemon=True).start()


def deploy_audit(audit: CodeGenAudit, *, admin_user) -> None:
    """
    Writes final_code files to a staging directory inside the target app:
        apps/{target_app}/codegen_output/
    Never overwrites existing production files.
    The developer reviews the staged files and manually applies changes.
    Raises ValueError for invalid paths. Raises RuntimeError on write failure.
    """
    code = audit.final_code or audit.generated_code
    if not code:
        raise ValueError("No hay código para desplegar en este audit entry.")

    app_dir = BASE_APPS_DIR / audit.target_app
    if not app_dir.exists():
        raise ValueError(
            f"El directorio '{app_dir}' no existe. "
            f"Verifica que target_app='{audit.target_app}' sea correcto."
        )

    # Write to staging subdirectory — never touch production files
    staging_dir = app_dir / "codegen_output"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Validate all paths stay inside apps/
    for filename in code:
        target = (staging_dir / filename).resolve()
        if not str(target).startswith(str(BASE_APPS_DIR.resolve())):
            raise ValueError(f"Ruta inválida detectada: {filename}")

    # Write staged files (safe to overwrite previous staging output)
    try:
        for filename, content in code.items():
            (staging_dir / filename).write_text(content, encoding="utf-8")
    except OSError as exc:
        audit.status = CodeGenAudit.Status.FAILED
        audit.deploy_error = str(exc)
        audit.save(update_fields=["status", "deploy_error"])
        raise RuntimeError(f"Error escribiendo archivos: {exc}") from exc

    # Update audit record
    audit.status = CodeGenAudit.Status.DEPLOYED
    audit.reviewed_by = admin_user
    audit.deployed_at = timezone.now()
    audit.save(update_fields=["status", "reviewed_by", "deployed_at"])

    # No container restart — files are staged, not applied to production.
    # Developer reviews apps/{target_app}/codegen_output/ and manually merges.
    logger.info(
        "deploy_audit: staged %d files for audit #%d → %s",
        len(code), audit.pk, staging_dir,
    )
