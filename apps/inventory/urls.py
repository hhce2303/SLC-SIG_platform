from django.urls import path

from apps.inventory.views import (
    ActivityLogListCreateView,
    ArticleDetailView,
    ArticleListCreateView,
    CamerasBySiteView,
    DashboardStatsView,
    GroupListView,
    InventorySSEView,
)

urlpatterns = [
    path("articles/", ArticleListCreateView.as_view(), name="inventory-articles"),
    path("articles/<int:article_id>/", ArticleDetailView.as_view(), name="inventory-article-detail"),
    path("groups/", GroupListView.as_view(), name="inventory-groups"),
    path("activity-logs/", ActivityLogListCreateView.as_view(), name="inventory-activity-logs"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="inventory-dashboard-stats"),
    path("cameras/by-site/<int:site_id>/", CamerasBySiteView.as_view(), name="inventory-cameras-by-site"),
    path("stream/", InventorySSEView.as_view(), name="inventory-sse-stream"),
]
