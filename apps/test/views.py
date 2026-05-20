from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.test.selectors import get_cameras_by_site
from apps.test.serializers import CameraReadSerializer

class CameraListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        site_id = 140
        cameras = get_cameras_by_site(site_id)
        serializer = CameraReadSerializer(cameras, many=True)
        return Response({"data": serializer.data, "total": len(serializer.data)})
