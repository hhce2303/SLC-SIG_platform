"""Inventory API views — thin orchestration layer."""

from __future__ import annotations

import json
import time

from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views import View

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory import selectors, services
from apps.inventory.serializers import (
    ActivityLogReadSerializer,
    ActivityLogWriteSerializer,
    ArticleReadSerializer,
    ArticleUpdateSerializer,
    ArticleWriteSerializer,
    CamerasBySiteSerializer,
    DashboardStatsSerializer,
    GroupSerializer,
)


class ArticleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_articles()
        data = ArticleReadSerializer(qs, many=True).data
        return Response({"data": data, "total": len(data)})

    def post(self, request: Request) -> Response:
        ser = ArticleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        article = services.create_article(data=ser.validated_data)
        return Response(
            ArticleReadSerializer(article).data,
            status=status.HTTP_201_CREATED,
        )


class ArticleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, article_id: int) -> Response:
        article = selectors.get_article_by_id(article_id)
        return Response(ArticleReadSerializer(article).data)

    def patch(self, request: Request, article_id: int) -> Response:
        ser = ArticleUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        article = services.update_article(article_id, data=ser.validated_data)
        return Response(ArticleReadSerializer(article).data)

    def delete(self, request: Request, article_id: int) -> Response:
        services.delete_article(article_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_groups()
        data = GroupSerializer(qs, many=True).data
        return Response({"data": data, "total": len(data)})


class ActivityLogListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        article_id = request.query_params.get("article_id")
        if article_id:
            qs = selectors.get_activity_logs_for_article(int(article_id))
        else:
            qs = selectors.get_activity_logs()
        data = ActivityLogReadSerializer(qs, many=True).data
        return Response({"data": data, "total": len(data)})

    def post(self, request: Request) -> Response:
        ser = ActivityLogWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        log = services.log_activity(data=ser.validated_data)
        return Response(
            ActivityLogReadSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        stats = selectors.get_dashboard_stats()
        return Response(DashboardStatsSerializer(stats).data)


class CamerasBySiteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        cameras = selectors.get_cameras_by_site(site_id)
        data = CamerasBySiteSerializer(cameras, many=True).data
        return Response({"data": data, "total": len(data)})


class InventorySSEView(View):
    """
    Server-Sent Events stream for real-time inventory updates.
    Polls DB every 5 s and pushes changed articles/groups/companies to all
    connected clients.  No django-channels required.
    """

    POLL_INTERVAL = 5  # seconds between DB checks

    def get(self, request):
        def event_stream():
            last_check = timezone.now()
            # Send an initial heartbeat so the connection is confirmed
            yield "event: connected\ndata: {}\n\n"

            while True:
                time.sleep(self.POLL_INTERVAL)
                now = timezone.now()

                # Changed articles
                changed = selectors.get_articles_updated_since(last_check)
                if changed.exists():
                    payload = ArticleReadSerializer(changed, many=True).data
                    yield f"event: articles_updated\ndata: {json.dumps(payload)}\n\n"

                last_check = now

                # Heartbeat keeps connection alive through proxies
                yield ": heartbeat\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
