"""
CodeGen services — main pipeline:
  1. get_schema_context()   (schema_inspector.py)
  2. build_ollama_prompt()  (Claude as prompt engineer — Haiku)
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
import shutil
import socket
import threading
import time
from pathlib import Path

import anthropic
import requests
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.codegen.models import CodeGenAudit
from apps.codegen.schema_inspector import get_schema_context

logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL    = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.100:11434")
OLLAMA_MODEL       = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:14b")
OLLAMA_TIMEOUT     = int(os.environ.get("OLLAMA_TIMEOUT", "300"))   # 5 min for large models
BASE_APPS_DIR      = Path(os.environ.get("BASE_APPS_DIR", "/app/apps"))
BACKUP_DIR         = Path(os.environ.get("CODEGEN_BACKUP_DIR", "/app/codegen_backups"))
DOCKER_CONTAINER   = os.environ.get("DOCKER_CONTAINER_NAME", "SIGplatform-web")

_claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""), max_retries=0)

# ---------------------------------------------------------------------------
# Few-shot examples extracted from actual project patterns
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

def build_ollama_prompt(user_request: str, schema: dict) -> str:
    """
    Uses Claude Haiku to construct an optimized few-shot prompt
    for the local model (qwen2.5-coder:14b).
    """
    schema_lines = []
    for table, info in schema.items():
        cols = [c["name"] for c in info["columns"]]
        fks  = [fk["references"] for fk in info["foreign_keys"]]
        schema_lines.append(
            f"Tabla '{table}': columnas={cols}"
            + (f", FK hacia={fks}" if fks else "")
        )
    schema_str = "\n".join(schema_lines)

    resp = _claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2000,
        system=f"""
Eres un prompt engineer especializado en generación de código Django/DRF.
Tu ÚNICA tarea es construir un prompt estructurado para un modelo de código local (qwen2.5-coder:14b).

{ARCHITECTURE_RULES}

EJEMPLOS REALES DEL PROYECTO PARA EL FEW-SHOT:
{FEW_SHOT_EXAMPLES}

FORMATO OBLIGATORIO para el output del modelo local:
El modelo debe envolver cada archivo así:
=== selectors.py ===
<código>
=== serializers.py ===
<código>
=== views.py ===
<código>
=== urls.py ===
<código>

Construye el prompt con:
1. Los ejemplos few-shot más relevantes para el request
2. El schema de DB específico (columnas, FKs)
3. La instrucción clara de qué generar
4. El formato de output esperado

Devuelve SOLO el prompt listo para enviar al modelo. Sin explicaciones.
""",
        messages=[{
            "role": "user",
            "content": (
                f"Request del usuario: {user_request}\n\n"
                f"Schema de tablas relevantes:\n{schema_str}"
            ),
        }],
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Step 3: Call local Ollama model
# ---------------------------------------------------------------------------

def call_local_model(prompt: str) -> dict:
    """
    Sends the structured prompt to Ollama on the dedicated PC (LAN).
    Returns parsed dict of {filename: code}.
    """
    try:
        resp = requests.post(
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
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"No se pudo conectar con Ollama en {OLLAMA_BASE_URL}. "
            "Verifica que el PC dedicado esté encendido y Ollama corriendo."
        ) from exc
    except requests.exceptions.Timeout as exc:
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
    """
    files: dict[str, str] = {}
    pattern = r"===\s*([\w.]+\.py)\s*===\n(.*?)(?===\s*[\w.]+\.py\s*===|\Z)"
    for match in re.finditer(pattern, raw, re.DOTALL):
        filename = match.group(1).strip()
        code = match.group(2).strip()
        if code:
            files[filename] = code
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
    # 1. Schema introspection
    schema = get_schema_context(tables if tables else None)

    # 2. Claude builds the structured prompt
    claude_prompt = build_ollama_prompt(user_request, schema)

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
        audit.save(update_fields=["status", "deploy_error"])
        raise

    # 5. Persist results
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
    Writes final_code files to the target app directory and restarts the service.
    Creates backups of existing files before overwriting.
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

    # Validate all paths stay inside apps/
    for filename in code:
        target = (app_dir / filename).resolve()
        if not str(target).startswith(str(BASE_APPS_DIR.resolve())):
            raise ValueError(f"Ruta inválida detectada: {filename}")

    # Backup existing files
    backup_dir = BACKUP_DIR / str(audit.pk)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for filename in code:
        original = app_dir / filename
        if original.exists():
            shutil.copy2(original, backup_dir / filename)

    # Write files
    try:
        for filename, content in code.items():
            (app_dir / filename).write_text(content, encoding="utf-8")
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

    # Restart container (15s delay — gives time to send the HTTP response first)
    _restart_container(delay=15)
    logger.info("deploy_audit: deployed %d files for audit #%d", len(code), audit.pk)
