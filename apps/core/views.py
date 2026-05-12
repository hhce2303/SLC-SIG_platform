from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import selectors
from apps.core.serializers import ActivityCatalogSerializer, SiteCatalogSerializer


class SiteListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: SiteCatalogSerializer(many=True)},
        summary="Listar sitios (catálogo)",
        description="Retorna todos los sitios con formato 'ID - site_name'.",
    )
    def get(self, request: Request) -> Response:
        data = selectors.get_all_sites()
        return Response(data)


class ActivityListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ActivityCatalogSerializer(many=True)},
        summary="Listar actividades (catálogo)",
        description="Retorna todas las actividades disponibles.",
    )
    def get(self, request: Request) -> Response:
        data = selectors.get_all_activities()
        return Response(data)
