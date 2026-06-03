"""
Helpers HTTP para views DRF: validación de query params y manejo de 404.

Objetivo: que el frontend reciba 400/404 claros en vez de 500 cuando manda
un parámetro inválido o pide un recurso inexistente.
"""

import logging

from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

from apps.core.pagination import StandardPagination

logger = logging.getLogger(__name__)

# Tope de seguridad para listados sin paginación: nunca materializar más de
# esto en memoria, aunque la tabla sea enorme (evita congelar el worker).
LIST_SAFETY_CAP = 1000


def parse_int_param(value, field: str = "parameter") -> int | None:
    """
    Convierte un query param a int.
    - None o cadena vacía → None (parámetro ausente, no es error).
    - No convertible → ValidationError (DRF responde 400, no 500).
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field: f"Debe ser un entero válido (recibido: {value!r})."})


def build_list_payload(request, qs, serializer_class, *, items_key="data", count_key="total") -> dict:
    """
    Construye el payload de un listado preservando el shape del endpoint
    ({items_key: [...], count_key: N}).

    - `count_key` siempre refleja el total real vía qs.count() (no len de lo
      serializado), evitando materializar la tabla dos veces.
    - Si la request trae `?page=`, pagina con StandardPagination (opt-in).
    - Si no, devuelve hasta LIST_SAFETY_CAP filas (válvula anti-congelamiento).
    """
    total = qs.count() if isinstance(qs, QuerySet) else len(qs)

    if request.query_params.get("page") is not None:
        paginator = StandardPagination()
        page_items = paginator.paginate_queryset(qs, request)
        data = serializer_class(page_items, many=True).data
        return {items_key: list(data), count_key: total}

    items = qs[:LIST_SAFETY_CAP]
    if total > LIST_SAFETY_CAP:
        logger.warning(
            "Listado %s truncado a %s de %s filas (usa ?page= para paginar).",
            request.path, LIST_SAFETY_CAP, total,
        )
    data = serializer_class(items, many=True).data
    return {items_key: list(data), count_key: total}
