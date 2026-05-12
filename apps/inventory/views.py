"""Inventory API views — thin orchestration layer."""

from __future__ import annotations

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
