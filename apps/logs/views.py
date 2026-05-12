from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.logs import selectors, services
from apps.logs.serializers import (
    CreateEventSerializer,
    DailyEventResponseSerializer,
)


class EventListCreateView(APIView):
    """
    GET  — shift events for the authenticated user (from last START SHIFT).
    POST — create a new daily event.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: DailyEventResponseSerializer(many=True)},
        summary="Listar eventos del turno actual",
        description=(
            "Retorna los eventos del usuario autenticado desde su último "
            "START SHIFT (activity_id=44). Respuesta envuelta en {data, total}."
        ),
    )
    def get(self, request: Request) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        qs = selectors.get_shift_events(daily_user.pk)
        serializer = DailyEventResponseSerializer(qs, many=True)

        return Response({
            "data": serializer.data,
            "total": len(serializer.data),
        })

    @extend_schema(
        request=CreateEventSerializer,
        responses={201: DailyEventResponseSerializer},
        summary="Crear evento diario",
        description=(
            "Crea un nuevo evento. El backend resuelve: usuario (JWT), "
            "event_datetime (now), event_status ('confirmed')."
        ),
    )
    def post(self, request: Request) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = CreateEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event = services.create_event(
            daily_user=daily_user,
            site_id=serializer.validated_data["site_id"],
            activity_id=serializer.validated_data["activity_id"],
            quantity=serializer.validated_data["quantity"],
            camera=serializer.validated_data.get("camera"),
            description=serializer.validated_data.get("description"),
        )

        response_data = DailyEventResponseSerializer(event).data
        return Response(response_data, status=status.HTTP_201_CREATED)
