"""Test Cameras API views — thin orchestration layer."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.test_cameras import selectors
from apps.test_cameras.serializers import CameraSerializer


class SiteCamerasListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        cameras = selectors.get_cameras_by_site(site_id)
        data = CameraSerializer(cameras, many=True).data
        return Response({"data": data, "total": len(data)})
