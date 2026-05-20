"""Sigtools API views — thin orchestration layer."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sigtools import selectors
from apps.sigtools.serializers import SiteSerializer


class SiteListView(APIView):
    """GET /api/v1/sigtools/sites/ — lista todos los sitios (id, name)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        sites = selectors.get_all_sites()
        serializer = SiteSerializer(sites, many=True)
        return Response(serializer.data)


class SiteDetailView(APIView):
    """GET /api/v1/sigtools/sites/{id}/ — obtiene un sitio por ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        site = selectors.get_site_by_id(site_id)
        if not site:
            return Response({"detail": "Site not found."}, status=404)
        serializer = SiteSerializer(site)
        return Response(serializer.data)
