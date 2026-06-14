"""
Helper async para Server-Sent Events sobre Redis pub/sub.

Cada cliente SSE:
  1. Se autentica UNA SOLA VEZ al abrir la conexión vía cookie sig_token o JWT.
  2. Se suscribe a un canal Redis y escucha mensajes.
  3. NO toca el ORM / MySQL durante el loop.
  4. Limpia la suscripción Redis en el finally (sin fugas).

Front-end: usar EventSource con { withCredentials: true } para enviar la cookie.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import redis.asyncio as aioredis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse

logger = logging.getLogger(__name__)

HEARTBEAT_SECS = 15  # bien por debajo del watchdog del front (60 s); fuerza flush periódico
MSG_TIMEOUT = 1.0    # máximo tiempo bloqueado esperando un mensaje Redis


@sync_to_async
def _resolve_user(request) -> bool:
    """
    Valida la identidad del cliente SSE UNA vez al abrir la conexión.
    Acepta dos mecanismos (en orden de prioridad):
      1. Cookie sig_token  → valida via Sanctum (SigtoolsCookieAuthentication)
      2. JWT Bearer        → valida via simplejwt (DailyUser)
    Retorna True si autenticado, False si no.
    """
    # --- 1. Cookie Sigtools ---
    cookie_name = getattr(settings, "SIGTOOLS_COOKIE_NAME", "sig_token")
    client_token = request.COOKIES.get(cookie_name)
    if client_token:
        from apps.sigtools_auth import token_utils
        pat = token_utils.validate_token(client_token)
        if pat is not None:
            return True

    # --- 2. JWT Bearer ---
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:].strip()
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            AccessToken(bearer)  # lanza si inválido
            return True
        except Exception:
            pass

    return False


async def sse_stream(channels: "str | list[str]", request) -> HttpResponse:
    """
    Autentica al cliente y devuelve un StreamingHttpResponse text/event-stream,
    o un 401 si no está autenticado. `channels` puede ser un canal único (str)
    o varios (list) — el stream multiplexa todos en una sola conexión.
    """
    authenticated = await _resolve_user(request)
    if not authenticated:
        return HttpResponse(status=401)

    chans = [channels] if isinstance(channels, str) else list(channels)
    response = StreamingHttpResponse(
        _event_generator(chans, request),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def _client_disconnected(request) -> bool:
    """
    Best-effort disconnect check.
    En algunos runtimes ASGIRequest no expone is_disconnected(); en ese caso
    devolvemos False y dejamos que el stream continúe normalmente.
    """
    fn = getattr(request, "is_disconnected", None)
    if not callable(fn):
        return False
    try:
        return await fn()
    except Exception:
        return False


async def _event_generator(channels: list[str], request):
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(*channels)
    last_beat = time.monotonic()

    try:
        yield "event: connected\ndata: {}\n\n"
        # Heartbeat inmediato: confirma el pipe y resetea el watchdog del front
        # desde el primer instante (no esperar HEARTBEAT_SECS).
        yield "event: heartbeat\ndata: {}\n\n"

        while True:
            if await _client_disconnected(request):
                break

            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=MSG_TIMEOUT,
            )
            if msg and msg.get("type") == "message":
                try:
                    env = json.loads(msg["data"])
                    yield f"event: {env['event']}\ndata: {json.dumps(env['data'])}\n\n"
                except (KeyError, json.JSONDecodeError) as exc:
                    logger.warning("sse bad message on %s: %s", channels, exc)

            now = time.monotonic()
            if now - last_beat >= HEARTBEAT_SECS:
                # Evento NOMBRADO (no comentario): el front resetea su watchdog
                # con addEventListener('heartbeat', ...). Un comentario ": ..."
                # mantiene viva la conexión TCP pero NO dispara evento JS.
                yield "event: heartbeat\ndata: {}\n\n"
                last_beat = now

    except asyncio.CancelledError:
        raise  # re-propagar después del finally
    finally:
        try:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()
            await client.aclose()
        except Exception:
            pass
