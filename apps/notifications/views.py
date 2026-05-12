"""
Views for supervisor specials.

Throttle note: these endpoints are deliberately designed for manual/infrequent
use (supervisor reviewing their queue). The frontend MUST NOT poll faster than
once every 30 seconds. If shared-cache throttling is needed in the future,
configure Django's Redis cache backend and enable DEFAULT_THROTTLE_CLASSES in
settings.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSupervisor
from apps.notifications import selectors, services
from apps.notifications.models import Special
from apps.notifications.serializers import MarkSpecialSerializer, SpecialResponseSerializer


class SupervisorSpecialsListView(APIView):
    """
    GET /api/v1/specials/supervisor/

    Returns the authenticated supervisor's pending specials (everything that
    is NOT 'done'). Response: { data: [...], total: N }
    """

    permission_classes = [IsAuthenticated, IsSupervisor]

    @extend_schema(
        responses={200: SpecialResponseSerializer(many=True)},
        summary="Listar specials pendientes del supervisor autenticado",
        description=(
            "Retorna los specials asignados al supervisor que NO tienen "
            "estado 'done'. Incluye nulos (sin marcar) y 'flagged'. "
            "Ordenados por spec_datetime DESC. Una sola query con JOINs — "
            "sin N+1."
        ),
        tags=["specials"],
    )
    def get(self, request: Request) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        qs = selectors.get_supervisor_pending_specials(daily_user.pk)
        serializer = SpecialResponseSerializer(qs, many=True)

        return Response({
            "data": serializer.data,
            "total": len(serializer.data),
        })


class SpecialMarkView(APIView):
    """
    PATCH /api/v1/specials/{id}/mark/

    Mark or unmark a special. Only the assigned supervisor can act on it.
    Send { "status": null } to unmark, { "status": "done" } or
    { "status": "flagged" } to mark.
    """

    permission_classes = [IsAuthenticated, IsSupervisor]

    @extend_schema(
        request=MarkSpecialSerializer,
        responses={200: SpecialResponseSerializer},
        summary="Marcar o desmarcar un special",
        description=(
            "Actualiza spec_status, spec_marked_at y spec_marked_by del special. "
            "Solo el supervisor asignado puede ejecutar esta acción. "
            "Enviar status=null para desmarcar (limpia los tres campos)."
        ),
        parameters=[
            OpenApiParameter(name="id", location="path", description="ID del special", required=True),
        ],
        tags=["specials"],
    )
    def patch(self, request: Request, pk: int) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = MarkSpecialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Authorization: only the assigned supervisor may mark their own specials
        if not Special.objects.filter(pk=pk, supervisor_id=daily_user.pk).exists():
            return Response(
                {"detail": "Special no encontrado o no asignado a este supervisor."},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = services.mark_special(
            special_id=pk,
            status=serializer.validated_data["status"],
            marked_by_id=daily_user.pk,
        )

        return Response(SpecialResponseSerializer(updated).data)
