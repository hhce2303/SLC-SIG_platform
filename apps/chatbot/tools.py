"""
Tool catalog for the chatbot.

Each entry in TOOL_SCHEMAS is sent to Claude so it knows what it can invoke.
HANDLERS maps tool name → Python function that executes the real operation.
WRITE_TOOLS lists names that require is_staff to execute.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from apps.installations import selectors as sel
from apps.core.exceptions import ResourceNotFound

# ---------------------------------------------------------------------------
# Tool schemas (sent to Claude)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_customer_groups",
        "description": "Lista grupos de clientes. limit: máx resultados (def 5).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 5)."}},
            "required": [],
        },
    },
    {
        "name": "list_sig_projects",
        "description": "Lista proyectos SIG activos con estado y versión. limit: máx resultados (def 5).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 5)."}},
            "required": [],
        },
    },
    {
        "name": "list_admin_users",
        "description": "Lista usuarios administradores con sus roles. limit: máx resultados (def 5).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 5)."}},
            "required": [],
        },
    },
    {
        "name": "list_admin_roles",
        "description": "Lista roles de administración con sus permisos. limit: máx resultados (def 5).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 5)."}},
            "required": [],
        },
    },
    {
        "name": "list_admin_permissions",
        "description": "Lista permisos disponibles en el sistema. limit: máx resultados (def 10).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 10)."}},
            "required": [],
        },
    },
    {
        "name": "get_site_status",
        "description": "Estado detallado de un sitio: dispositivos, cámaras, servidores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "integer", "description": "ID del sitio."},
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "get_installation_types",
        "description": "Lista tipos de instalación disponibles.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_sites",
        "description": "Lista sitios activos con nombre, ciudad, estado y conteo de cámaras. limit: máx resultados (def 10).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Máx resultados (def 10)."}},
            "required": [],
        },
    },
    {
        "name": "list_cameras",
        "description": "Lista cámaras de SIG Tools. Filtros opcionales: site_id, brand, camera_type, limit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "integer", "description": "ID del sitio."},
                "brand": {"type": "string", "description": "Marca (parcial)."},
                "camera_type": {"type": "string", "description": "Tipo de cámara (parcial)."},
                "limit": {"type": "integer", "description": "Máx resultados (def 100, máx 500)."},
            },
            "required": [],
        },
    },
    {
        "name": "restart_service",
        "description": "Reinicia el contenedor web. Usar solo tras escribir archivos nuevos. Avisa al usuario antes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_project_file",
        "description": "Lee un archivo del proyecto (ruta relativa). No lee .env ni credenciales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta relativa (ej. apps/inventory/views.py)."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_project_directory",
        "description": "Lista archivos y carpetas en un directorio del proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta relativa al directorio. Vacío para raíz."},
            },
            "required": [],
        },
    },
    {
        "name": "write_project_file",
        "description": "Crea o sobreescribe un archivo dentro de apps/ solamente. Para config/* mostrar en texto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta dentro de apps/ (ej. apps/myapp/views.py)."},
                "content": {"type": "string", "description": "Contenido completo del archivo."},
                "overwrite": {"type": "boolean", "description": "Sobreescribir si existe. Default false."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_django_check",
        "description": "Ejecuta manage.py check para validar el proyecto tras crear archivos.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_endpoint",
        "description": (
            "Genera automáticamente código Django (selector, serializer, view, urls) "
            "usando el modelo local de IA (Ollama + qwen2.5-coder). "
            "Usa esto cuando el usuario pida crear un endpoint nuevo y quiera usar la IA local. "
            "El resultado queda en el audit log para revisión del admin antes de desplegarse. "
            "Requiere: user_request (descripción del endpoint), target_app (nombre del app Django destino). "
            "Opcional: tables_used (lista de tablas MySQL relevantes para el schema)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "Descripción clara del endpoint a generar (ej: 'endpoint GET para listar cámaras activas de un site').",
                },
                "target_app": {
                    "type": "string",
                    "description": "Nombre del app Django donde se generará el código (ej: 'cameras', 'inventory').",
                },
                "tables_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tablas MySQL a usar como contexto del schema (opcional).",
                },
            },
            "required": ["user_request", "target_app"],
        },
    },
    {
        "name": "list_codegen_audits",
        "description": "Lista los últimos registros del audit log de generación de código. Muestra estado (pending/approved/deployed/rejected) y el request original.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtrar por estado: pending, approved, modified, rejected, deployed, failed. Vacío = todos.",
                },
                "limit": {"type": "integer", "description": "Máx resultados (def 10)."},
            },
            "required": [],
        },
    },
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _list_customer_groups(inputs: dict, user) -> Any:
    groups = sel.get_customer_groups()
    return {"count": len(groups), "groups": groups}


def _list_sig_projects(inputs: dict, user) -> Any:
    projects = sel.list_sig_projects()
    return {"count": len(projects), "projects": projects}


def _list_admin_users(inputs: dict, user) -> Any:
    users = sel.list_admin_users()
    return {"count": len(users), "users": users}


def _list_admin_roles(inputs: dict, user) -> Any:
    roles = sel.list_admin_roles()
    return {"count": len(roles), "roles": roles}


def _list_admin_permissions(inputs: dict, user) -> Any:
    perms = sel.list_admin_permissions()
    return {"count": len(perms), "permissions": perms}


def _get_site_status(inputs: dict, user) -> Any:
    site_id = int(inputs["site_id"])
    result = sel.get_site_status(site_id)
    if not result:
        raise ResourceNotFound(f"Sitio con ID {site_id} no encontrado.")
    return {"site_id": site_id, "devices": result}


def _get_installation_types(inputs: dict, user) -> Any:
    types = sel.get_installation_types()
    return {"count": len(types), "types": types}


def _list_sites(inputs: dict, user) -> Any:
    limit = int(inputs.get("limit", 10))
    sites = sel.list_sites()
    total = len(sites)
    return {"total": total, "showing": min(limit, total), "sites": sites[:limit]}


def _list_cameras(inputs: dict, user) -> Any:
    site_id     = inputs.get("site_id")
    brand       = inputs.get("brand")
    camera_type = inputs.get("camera_type")
    limit       = int(inputs.get("limit", 100))
    cameras = sel.list_cameras(
        site_id=site_id,
        brand=brand,
        camera_type=camera_type,
        limit=limit,
    )
    return {"count": len(cameras), "cameras": cameras}


# ---------------------------------------------------------------------------
# Code generation helpers
# ---------------------------------------------------------------------------

def _get_project_root() -> Path:
    """Returns the Django project root (BASE_DIR)."""
    from django.conf import settings
    return Path(settings.BASE_DIR).resolve()


def _validate_read_path(rel_path: str) -> Path:
    """
    Validates a read path:
    - Must be relative (no absolute paths)
    - Must stay within project root (no traversal)
    - Cannot read .env or credential files
    """
    if not rel_path or not rel_path.strip():
        raise ValueError("Path cannot be empty.")
    norm = Path(rel_path)
    if norm.is_absolute():
        raise ValueError("Path must be relative, not absolute.")
    root = _get_project_root()
    abs_path = (root / norm).resolve()
    # Prevent path traversal
    if not str(abs_path).startswith(str(root)):
        raise ValueError("Path traversal is not permitted.")
    # Block sensitive files
    name = abs_path.name.lower()
    if name == ".env" or name.endswith(".env") or name in ("secrets.py", "local_settings.py"):
        raise ValueError("Reading credential/secret files is not permitted.")
    return abs_path


def _validate_write_path(rel_path: str) -> Path:
    """
    Validates a write path:
    - Must be relative
    - Must resolve to within apps/ or config/ directory
    - No path traversal
    """
    if not rel_path or not rel_path.strip():
        raise ValueError("Path cannot be empty.")
    norm = Path(rel_path)
    if norm.is_absolute():
        raise ValueError("Path must be relative, not absolute.")
    root = _get_project_root()
    abs_path = (root / norm).resolve()
    apps_dir   = (root / "apps").resolve()
    config_dir = (root / "config").resolve()
    inside_apps   = str(abs_path).startswith(str(apps_dir) + os.sep) or abs_path == apps_dir
    inside_config = str(abs_path).startswith(str(config_dir) + os.sep) or abs_path == config_dir
    if not inside_apps and not inside_config:
        raise ValueError(
            f"Write access is restricted to apps/ and config/ directories."
        )
    return abs_path


def _read_project_file(inputs: dict, user) -> Any:
    rel_path = inputs.get("path", "").strip()
    try:
        abs_path = _validate_read_path(rel_path)
    except ValueError as exc:
        raise exc
    if not abs_path.exists():
        raise ValueError(f"File not found: {rel_path}")
    if not abs_path.is_file():
        raise ValueError(f"Not a file: {rel_path}")
    raw = abs_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    total = len(lines)
    # Truncate at 300 lines to avoid token overflow
    if total > 300:
        raw = "\n".join(lines[:300]) + f"\n\n# ... [{total - 300} more lines — read again with a narrower range if needed]"
    return {"path": rel_path, "total_lines": total, "content": raw}


def _list_project_directory(inputs: dict, user) -> Any:
    rel_path = inputs.get("path", "").strip()
    root = _get_project_root()
    if rel_path:
        norm = Path(rel_path)
        if norm.is_absolute():
            raise ValueError("Path must be relative.")
        abs_path = (root / norm).resolve()
        if not str(abs_path).startswith(str(root)):
            raise ValueError("Path traversal is not permitted.")
    else:
        abs_path = root
    if not abs_path.is_dir():
        raise ValueError(f"Not a directory: {rel_path or '(project root)'}")
    items = []
    for item in sorted(abs_path.iterdir()):
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        items.append({"name": item.name, "type": "dir" if item.is_dir() else "file"})
    return {"path": rel_path or ".", "items": items}


def _write_project_file(inputs: dict, user) -> Any:
    rel_path = inputs.get("path", "").strip()
    content  = inputs.get("content", "")
    overwrite = bool(inputs.get("overwrite", False))
    abs_path = _validate_write_path(rel_path)  # raises if outside apps/
    existed = abs_path.exists()
    if existed and not overwrite:
        raise ValueError(
            f"El archivo ya existe: {rel_path}. "
            f"Usa overwrite=true para reemplazarlo, o elige un nombre distinto."
        )
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return {
        "path": rel_path,
        "action": "updated" if existed else "created",
        "bytes": len(content.encode("utf-8")),
    }


def _restart_service(inputs: dict, user) -> Any:
    """
    Restarts the web container (daily-log-backend) via the Docker Engine API
    over the UNIX socket — no docker CLI binary required.
    Returns immediately; the actual restart fires ~2 s later so the HTTP
    response can be flushed to the client before the connection drops.
    """
    import http.client
    import socket as _socket
    import threading
    import time

    # Quick pre-flight: verify socket is accessible before promising a restart
    sock_path = "/var/run/docker.sock"
    if not os.path.exists(sock_path):
        raise ValueError(
            "Docker socket no encontrado en /var/run/docker.sock. "
            "El contenedor debe tener el socket montado para reiniciarse."
        )

    class _UnixHTTPConnection(http.client.HTTPConnection):
        """HTTPConnection that connects through a UNIX domain socket."""
        def __init__(self, socket_path: str):
            super().__init__("localhost")
            self._socket_path = socket_path

        def connect(self):
            self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.sock.connect(self._socket_path)

    def _do_restart():
        time.sleep(15)  # Give Claude time to finish the response before restarting
        try:
            conn = _UnixHTTPConnection(sock_path)
            # t=5 → 5-second grace period before SIGKILL
            conn.request("POST", "/containers/daily-log-backend/restart?t=5")
            conn.getresponse()
        except Exception:
            pass  # Container restarted — this thread dies naturally

    t = threading.Thread(target=_do_restart, daemon=True)
    t.start()
    return {
        "status": "restarting",
        "message": (
            "Reinicio programado en 15 segundos. "
            "La conexión se interrumpirá unos 5-10 segundos — es normal."
        ),
    }


def _run_django_check(inputs: dict, user) -> Any:
    root = _get_project_root()
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": (result.stdout + result.stderr)[:3000],
    }


def _generate_endpoint(inputs: dict, user) -> Any:
    """
    Triggers the full AI code generation pipeline:
      schema_inspector → Claude prompt engineering → Ollama local model → AuditLog
    Blocks until Ollama responds (~45-90s with GPU on dedicated PC).
    Returns the generated code so Claude can display it directly in the chat.
    """
    from apps.codegen.services import generate_code

    user_request = inputs.get("user_request", "").strip()
    target_app   = inputs.get("target_app", "").strip()
    tables_used  = inputs.get("tables_used", [])

    if not user_request:
        raise ValueError("user_request es requerido.")
    if not target_app:
        raise ValueError("target_app es requerido.")

    audit = generate_code(
        user_request=user_request,
        target_app=target_app,
        tables=tables_used,
    )

    files_generated = list(audit.generated_code.keys()) if audit.generated_code else []

    # Build readable code sections for Claude to display in chat
    code_sections: list[str] = []
    for filename, code in (audit.generated_code or {}).items():
        code_sections.append(f"=== {filename} ===\n```python\n{code}\n```")
    code_display = "\n\n".join(code_sections) if code_sections else "Sin código generado — revisar logs."

    return {
        "audit_id": audit.pk,
        "status": audit.status,
        "target_app": audit.target_app,
        "files_generated": files_generated,
        "generated_code": code_display,
        "approve_url": f"/api/v1/codegen/audits/{audit.pk}/approve/",
        "note": (
            f"Código generado en audit #{audit.pk}. "
            f"Para desplegarlo: POST {'/api/v1/codegen/audits/' + str(audit.pk) + '/approve/'}"
        ),
    }


def _list_codegen_audits(inputs: dict, user) -> Any:
    from apps.codegen.models import CodeGenAudit

    limit  = int(inputs.get("limit", 10))
    status = inputs.get("status", "").strip()

    qs = CodeGenAudit.objects.select_related("reviewed_by").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)

    audits = qs[:limit]
    return {
        "total": qs.count(),
        "showing": len(audits),
        "audits": [
            {
                "id": a.pk,
                "status": a.status,
                "target_app": a.target_app,
                "user_request": a.user_request[:120],
                "files": list(a.generated_code.keys()),
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
                "reviewed_by": a.reviewed_by.username if a.reviewed_by else None,
            }
            for a in audits
        ],
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

# Tools that require is_staff to execute
WRITE_TOOLS: set[str] = {"write_project_file", "restart_service", "generate_endpoint"}

HANDLERS: dict[str, Any] = {
    "list_customer_groups":   _list_customer_groups,
    "list_sig_projects":      _list_sig_projects,
    "list_admin_users":       _list_admin_users,
    "list_admin_roles":       _list_admin_roles,
    "list_admin_permissions": _list_admin_permissions,
    "get_site_status":        _get_site_status,
    "get_installation_types": _get_installation_types,
    "list_sites":             _list_sites,
    "list_cameras":           _list_cameras,
    # Service management
    "restart_service":        _restart_service,
    # Code generation (manual)
    "read_project_file":      _read_project_file,
    "list_project_directory": _list_project_directory,
    "write_project_file":     _write_project_file,
    "run_django_check":       _run_django_check,
    # AI-powered code generation
    "generate_endpoint":      _generate_endpoint,
    "list_codegen_audits":    _list_codegen_audits,
}


def dispatch(name: str, inputs: dict, user) -> Any:
    """
    Execute a tool by name.
    Raises ValueError for unknown tools.
    Raises PermissionError if the user lacks is_staff for write tools.
    """
    if name not in HANDLERS:
        raise ValueError(f"Herramienta desconocida: '{name}'")

    if name in WRITE_TOOLS and not getattr(user, "is_staff", False):
        raise PermissionError(f"No tienes permisos para ejecutar '{name}'.")

    return HANDLERS[name](inputs, user)
