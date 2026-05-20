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

import logging
import os
import json
import time
from typing import Any

import anthropic

from . import tools as tool_registry

logger = logging.getLogger(__name__)

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
        _client = anthropic.Anthropic(api_key=_API_KEY, max_retries=0)
    return _client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
Eres el asistente de administración de SIG Systems (monitoreo de seguridad).
Responde en español. Usa herramientas para datos reales — nunca inventes.

PERSONALIDAD Y TONO:
- Amigable pero profesional, como colega de confianza del equipo técnico.
- Al saludar: algo tipo "¡Hola mi compa! ¿Cómo te puedo ayudar el día de hoy?"
- Cuando puedas confirmar algo: primero di "Listo, ya estuvo." o "Listo." y LUEGO lo técnico.
- Frases cortas. Sin rodeos. Si ya funciona, dilo antes de explicar cómo.
- No uses lenguaje corporativo ni frases como "Por supuesto", "Entendido", "Con gusto".

PROYECTO: Django 5 + DRF. Raíz: /app (Docker).
BDs: default→sig_dailylogs | sigtools→sigtools_beta (MySQL).
Auth DRF: SigtoolsCookieAuthentication > JWTAuthentication. Permisos: IsAuthenticated.

ESTRUCTURA DE APP:
  apps/<nombre>/__init__.py, apps.py, models.py, serializers.py,
  selectors.py (lecturas), services.py (escrituras), views.py, urls.py, admin.py

PATRÓN VIEWS (APIView):
  class MiView(APIView):
      permission_classes = [IsAuthenticated]
      def get(self, request): return Response(MiSerializer(selectors.get(), many=True).data)

PATRÓN URLS:
  urlpatterns = [path("items/", MiView.as_view(), name="mi-list")]

PATRÓN APPS.PY:
  class MiAppConfig(AppConfig):
      name = "apps.<nombre>"

SQL sigtools (SIEMPRE %s, nunca f-string):
  with connections["sigtools"].cursor() as cur:
      cur.execute("SELECT id FROM tabla WHERE x=%s", [val])
      cols=[c[0] for c in cur.description]
      return [dict(zip(cols,r)) for r in cur.fetchall()]

WORKFLOW ENDPOINT NUEVO (write_project_file — solo si usuario pide escribir código directamente):
1. list_project_directory("apps") → ver apps existentes
2. read_project_file("apps/<app>/views.py") → verificar si el endpoint YA EXISTE en el código
3. read_project_file("config/urls.py") → verificar si el app está REGISTRADO en api_v1
4. Si no existe → write_project_file para cada archivo en apps/<nueva_app>/
5. Si es app nueva → write_project_file también para config/settings/base.py (agregar "apps.<nueva_app>" a LOCAL_APPS) y config/urls.py (agregar path en api_v1)
6. run_django_check → validar

write_project_file: permitido en apps/ Y config/. Úsalo para todos los archivos necesarios.
Endpoints bajo: /api/v1/<prefix>/

CRÍTICO: Nunca digas que un endpoint "ya existe y funciona" sin verificar AMBAS condiciones:
  a) El código existe en apps/<app>/views.py (usar read_project_file)
  b) El app está registrado en config/urls.py (usar read_project_file)
Si falta (b), usar write_project_file para agregar el path en config/urls.py.

write_project_file: permitido en apps/ Y config/.
Endpoints bajo: /api/v1/<prefix>/

GENERACIÓN DE ENDPOINT CON IA (generate_endpoint — PREDETERMINADO para cualquier solicitud de nuevo endpoint):
Cuando el usuario pida generar, crear, o hacer un endpoint nuevo, USA generate_endpoint POR DEFECTO.
NO asumir que el endpoint ya existe. NO usar write_project_file para generar código nuevo.
Pasos:
1. Confirmar internamente: target_app (app Django destino) y tablas relevantes — si no están claros, preguntar antes
2. Avisar que tarda ~1-2 min (modelo local generando) y que espere
3. Llamar generate_endpoint con {user_request, target_app, tables_used}
4. Al recibir el resultado, COPIAR TEXTUALMENTE el campo "generated_code" DEL TOOL RESULT — SIN RESUMIR, SIN OMITIR NADA.
   REGLA CRÍTICA: el campo "generated_code" ya contiene los bloques de código formateados. Pégalo tal cual en tu respuesta.
   NO digas "aquí está el código" y luego describas — MUESTRA el código completo.
5. Al final agrega en una línea: "Audit ID: {id} | Para desplegar: POST {approve_url}"
6. El chatbot NO despliega automáticamente — solo el admin aprueba vía API""".strip()

# ---------------------------------------------------------------------------
# Model — always Haiku; heavy code generation is offloaded to local Ollama model
# ---------------------------------------------------------------------------

_MODEL_HAIKU = "claude-haiku-4-5"


def _pick_model(message: str) -> str:  # signature kept for compatibility
    return _MODEL_HAIKU

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
    model  = _pick_model(message)

    # Keep only the last 6 history turns (3 user+assistant pairs) to limit token growth.
    # Full history can carry 5-10K tokens of prior tool results that Claude doesn't need.
    trimmed_history = list(history)[-6:]
    messages: list[dict] = trimmed_history + [{"role": "user", "content": message}]

    for _ in range(_MAX_TOOL_ROUNDS):
        response = _create_with_retry(client, messages, model)

        # Pure text response — done
        if response.stop_reason == "end_turn":
            return _extract_text(response)

        # Claude wants to call tools
        if response.stop_reason == "tool_use":
            tool_results = _execute_tool_calls(response, user)

            # Before appending, compress old tool_result messages (keep only last round fresh).
            # This prevents accumulating large JSON payloads across many tool rounds.
            _compress_old_tool_results(messages)

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

_RETRY_DELAYS = (15, 30, 60)  # seconds to wait on successive 429s


def _compress_old_tool_results(messages: list[dict], max_chars: int = 300) -> None:
    """
    Replace content of tool_result blocks in all but the last user message
    with a short summary. This prevents old large JSON results from being
    re-sent on every subsequent API call.
    """
    # Find indices of user messages that contain tool_result blocks
    tool_result_indices = [
        i for i, m in enumerate(messages)
        if m["role"] == "user" and isinstance(m.get("content"), list)
        and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"])
    ]
    # Keep the most recent one intact — only compress older ones
    for idx in tool_result_indices[:-1]:
        compressed = []
        for block in messages[idx]["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                content = block.get("content", "")
                if isinstance(content, str) and len(content) > max_chars:
                    block = {**block, "content": content[:max_chars] + " …[comprimido]"}
            compressed.append(block)
        messages[idx] = {**messages[idx], "content": compressed}


def _create_with_retry(client: anthropic.Anthropic, messages: list[dict], model: str = _MODEL_HAIKU):
    """Call client.messages.create with one automatic retry on RateLimitError."""
    for attempt in range(2):
        try:
            return client.messages.create(
                model=model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=tool_registry.TOOL_SCHEMAS,
                messages=messages,
            )
        except anthropic.RateLimitError:
            if attempt == 0:
                logger.warning("Claude rate limit hit — esperando 65s antes de reintentar...")
                time.sleep(65)
                continue
            raise RuntimeError(
                "Límite de tokens alcanzado. Se reintentó automáticamente pero el límite persiste. "
                "Por favor espera 60 segundos e intenta de nuevo."
            )


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
