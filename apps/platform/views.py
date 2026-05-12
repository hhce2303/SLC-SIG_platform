from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform import services
from apps.platform.serializers import (
    PlatformLoginSerializer,
    PlatformLoginResponseSerializer,
    StationConfigQuerySerializer,
    StationConfigSerializer,
    ToolSerializer,
)


class PlatformLoginView(APIView):
    """
    Central platform login — username + password only, no station required.
    Returns JWT tokens valid for all connected tools.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=PlatformLoginSerializer,
        responses={200: PlatformLoginResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = PlatformLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = services.platform_login(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        return Response(result, status=status.HTTP_200_OK)


class PlatformToolsView(APIView):
    """
    Return the list of active tools accessible by the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ToolSerializer(many=True)})
    def get(self, request: Request) -> Response:
        tools = services.get_user_tools(request.user.pk)
        return Response(tools, status=status.HTTP_200_OK)


class StationConfigView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[StationConfigQuerySerializer],
        responses={200: StationConfigSerializer},
        summary="Resolver estación por station_number",
        description="Valida la estación enviada por el frontend y retorna su estado actual.",
    )
    def get(self, request: Request) -> Response:
        serializer = StationConfigQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        station_config = services.get_station_config(
            station_number=serializer.validated_data["station_number"],
        )
        return Response(station_config, status=status.HTTP_200_OK)
