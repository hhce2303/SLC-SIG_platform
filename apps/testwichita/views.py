"""Test Wichita API views."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.testwichita import selectors
from apps.testwichita.serializers import CameraSerializer


class WichitaCamerasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Get cameras for site 257 (DriveTime Wichita)."""
        cameras = selectors.get_cameras_for_site(site_id=257)
        data = CameraSerializer(cameras, many=True).data
        return Response({
            "site_id": 257,
            "site_name": "DriveTime Wichita",
            "total": len(data),
            "cameras": data,
        })
