"""Layers API views."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.layers import selectors
from apps.layers.serializers import LayerSerializer


class LayerListView(APIView):
    """GET /api/v1/layers/ — lista todos los layers (id, name)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        layers = selectors.get_all_layers()
        serializer = LayerSerializer(layers, many=True)
        return Response(serializer.data)
