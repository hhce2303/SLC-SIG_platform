from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.reports import selectors
from apps.reports.serializers import PoliceDispatchReadSerializer


class PoliceDispatchListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        limit = int(request.query_params.get("limit", 50))
        records = selectors.get_police_dispatch_events(limit=limit)
        serializer = PoliceDispatchReadSerializer(records, many=True)
        return Response({"data": serializer.data, "total": len(serializer.data)})
