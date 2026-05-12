"""
ChatbotService — integrates with the Claude API.

Flow:
  1. Receive user message + conversation history
  2. Send to Claude with tool schemas
  3. If Claude requests tool_use → dispatch to tools.py → send result back
  4. Repeat until Claude returns end_turn text response
  5. Return final text reply
"""
from __future__ import annotations

import os
import json
from typing import Any

import anthropic

from . import tools as tool_registry

# ---------------------------------------------------------------------------
# Client (initialised once at module load; fails fast if key is missing)
# ---------------------------------------------------------------------------

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not _API_KEY or _API_KEY.startswith("sk-ant-REPLACE"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY no está configurado. "
                "Agrega tu clave real en el archivo .env."
            )
        _client = anthropic.Anthropic(api_key=_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
Eres el asistente de administración de SIG Systems, una plataforma de monitoreo de seguridad.
Tienes acceso a herramientas para consultar datos del sistema en tiempo real Y para crear
nuevos endpoints en el proyecto Django.

════════════════════════════════════════════════════════════════════
REGLAS GENERALES
════════════════════════════════════════════════════════════════════
- Responde siempre en español, de forma clara y concisa.
- Usa las herramientas disponibles para obtener datos reales antes de responder.
- No inventes IDs, nombres ni datos — consulta siempre la base de datos.
- No ejecutes operaciones de escritura sin confirmación explícita del usuario.

════════════════════════════════════════════════════════════════════
ARQUITECTURA DEL PROYECTO (Django 5 + DRF)
════════════════════════════════════════════════════════════════════
Raíz del proyecto: /app  (en Docker)

Estructura de una app típica:
  apps/<nombre>/
    __init__.py
    apps.py          ← AppConfig
    models.py        ← Solo definición de datos, sin lógica
    serializers.py   ← Solo forma de datos, sin lógica
    selectors.py     ← Lecturas optimizadas de la BD (sin side-effects)
    services.py      ← Lógica de negocio (escribe en BD)
    views.py         ← Solo orquestación: deserializa → servicio/selector → Response
    urls.py          ← path() entries
    admin.py         ← Registros en el admin

Base de datos:
  - default  → sig_dailylogs (MySQL) — apps Django normales
  - sigtools  → sigtools_beta (MySQL) — datos de instalaciones/cámaras/sitios

Autenticación DRF (DEFAULT_AUTHENTICATION_CLASSES):
  1. SigtoolsCookieAuthentication  ← cookie sig_token (panel web sigtools)
  2. JWTAuthentication             ← token Bearer (mobile / API)
  Para vistas del admin Django usar también: SessionAuthentication

Permisos por defecto: IsAuthenticated

════════════════════════════════════════════════════════════════════
PATRONES DE CÓDIGO (OBLIGATORIOS)
════════════════════════════════════════════════════════════════════

## views.py — APIView pattern
```python
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from apps.<nombre> import selectors, services
from apps.<nombre>.serializers import MiSerializer

class MiListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        data = selectors.get_mis_items()
        return Response(MiSerializer(data, many=True).data)

    def post(self, request: Request) -> Response:
        ser = MiSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = services.crear_item(ser.validated_data)
        return Response(MiSerializer(obj).data, status=status.HTTP_201_CREATED)
```

## serializers.py — sin lógica
```python
from rest_framework import serializers
from apps.<nombre>.models import MiModelo

class MiSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiModelo
        fields = ("id", "nombre", "created_at")
```

## urls.py
```python
from django.urls import path
from apps.<nombre>.views import MiListView, MiDetailView

urlpatterns = [
    path("items/",           MiListView.as_view(),   name="mi-app-list"),
    path("items/<int:pk>/",  MiDetailView.as_view(), name="mi-app-detail"),
]
```

## apps.py
```python
from django.apps import AppConfig

class MiAppConfig(AppConfig):
    name = "apps.<nombre>"
    verbose_name = "<Nombre legible>"
```

## Consultas a sigtools_beta (BD externa)
```python
from django.db import connections
_DB = "sigtools"

def mis_datos() -> list[dict]:
    sql = "SELECT id, nombre FROM mi_tabla WHERE deleted_at IS NULL"
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
```
NUNCA usar f-strings o % en SQL. Siempre usar %s con parámetros.

════════════════════════════════════════════════════════════════════
WORKFLOW PARA CREAR UN NUEVO ENDPOINT
════════════════════════════════════════════════════════════════════
1. list_project_directory("apps") → explorar apps existentes
2. read_project_file de un app similar → copiar patrones exactos
3. write_project_file para cada archivo nuevo dentro de apps/<nueva_app>/
4. run_django_check → validar que no hay errores de importación
5. Mostrar al usuario (en tu respuesta de texto) las DOS líneas de config manual:

   **Paso manual 1** — En config/settings/base.py, agregar a LOCAL_APPS:
   ```python
   "apps.<nueva_app>",
   ```

   **Paso manual 2** — En config/urls.py, agregar a api_v1:
   ```python
   path("<prefix>/", include("apps.<nueva_app>.urls")),
   ```

IMPORTANTE: write_project_file solo puede escribir dentro de apps/.
Para config/settings/base.py y config/urls.py, siempre muéstralos en el texto.

════════════════════════════════════════════════════════════════════
URL BASE DE LA API
════════════════════════════════════════════════════════════════════
Todos los endpoints se montan bajo: /api/v1/<prefix>/
Ejemplos de endpoints existentes:
  /api/v1/inventory/articles/
  /api/v1/chatbot/message/
  /api/v1/installations/
""".strip()

_MAX_TOOL_ROUNDS = 15  # More rounds needed for code generation (read → write → check)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_message(message: str, history: list[dict], user) -> str:
    """
    Process a user message and return Claude's text reply.

    Args:
        message: The new user message.
        history: Previous turns as [{"role": "user"|"assistant", "content": str}, ...]
        user: Django request.user (used for permission checks in tools)

    Returns:
        Claude's final text response.
    """
    client = _get_client()

    # Build message list: history + new user message
    messages: list[dict] = list(history) + [{"role": "user", "content": message}]

    for _ in range(_MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=tool_registry.TOOL_SCHEMAS,
            messages=messages,
        )

        # Pure text response — done
        if response.stop_reason == "end_turn":
            return _extract_text(response)

        # Claude wants to call tools
        if response.stop_reason == "tool_use":
            tool_results = _execute_tool_calls(response, user)

            # Append Claude's response + tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    return "No pude completar la operación. Por favor intenta de nuevo."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _execute_tool_calls(response, user) -> list[dict]:
    """Execute all tool_use blocks in a response and return tool_result list."""
    results = []

    for block in response.content:
        if block.type != "tool_use":
            continue

        try:
            result = tool_registry.dispatch(block.name, block.input, user)
            # Truncate very large results to avoid token overflow
            content = _safe_serialize(result)
        except (PermissionError, ValueError) as exc:
            content = f"ERROR: {exc}"
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": True,
            })
            continue
        except Exception as exc:
            content = f"ERROR inesperado al ejecutar '{block.name}': {exc}"
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": True,
            })
            continue

        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": content,
        })

    return results


def _extract_text(response) -> str:
    """Extract the first text block from a Claude response."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _safe_serialize(data: Any, max_chars: int = 8000) -> str:
    """Serialize tool result to string, truncating if too large."""
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(data)

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [resultado truncado, {len(text)} chars total]"

    return text


def ping() -> dict:
    """
    Quick connectivity check — does NOT consume tokens.
    Returns model list from Anthropic to verify key + network.
    """
    client = _get_client()
    models = client.models.list()
    return {
        "status": "ok",
        "models_available": [m.id for m in models.data][:5],
    }
