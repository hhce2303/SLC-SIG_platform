from django.urls import path

from apps.inventory.views import (
    ActivityLogListCreateView,
    ArticleDetailView,
    ArticleListCreateView,
    CamerasBySiteView,
    DashboardStatsView,
    GroupListView,
    inventory_sse_stream,
    MaterialsRequestListCreateView,
    MaterialsRequestReviewView,
    DailyReportListCreateView,
    CableRunListCreateView,
    CableRunDetailView,
    ScopeChangeListCreateView,
    ScopeChangeDetailView,
    ScopeChangeReviewView,
    EquipmentReturnListCreateView,
    EquipmentReturnDetailView,
    EquipmentReturnReceiveView,
    OperationsAssignmentView,
    ElevatorRentalView,
)

urlpatterns = [
    path("articles/", ArticleListCreateView.as_view(), name="inventory-articles"),
    path("articles/<int:article_id>/", ArticleDetailView.as_view(), name="inventory-article-detail"),
    path("groups/", GroupListView.as_view(), name="inventory-groups"),
    path("activity-logs/", ActivityLogListCreateView.as_view(), name="inventory-activity-logs"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="inventory-dashboard-stats"),
    path("cameras/by-site/<int:site_id>/", CamerasBySiteView.as_view(), name="inventory-cameras-by-site"),
    path("stream/", inventory_sse_stream, name="inventory-sse-stream"),
    # Materials Requests
    path("materials-requests/", MaterialsRequestListCreateView.as_view(), name="inventory-materials-requests"),
    path("materials-requests/<int:request_id>/review/", MaterialsRequestReviewView.as_view(), name="inventory-materials-request-review"),
    # Daily Reports
    path("daily-reports/", DailyReportListCreateView.as_view(), name="inventory-daily-reports"),
    # Cable Runs
    path("cable-runs/", CableRunListCreateView.as_view(), name="inventory-cable-runs"),
    path("cable-runs/<int:cable_run_id>/", CableRunDetailView.as_view(), name="inventory-cable-run-detail"),
    # Scope Changes
    path("scope-changes/", ScopeChangeListCreateView.as_view(), name="inventory-scope-changes"),
    path("scope-changes/<int:scope_change_id>/", ScopeChangeDetailView.as_view(), name="inventory-scope-change-detail"),
    path("scope-changes/<int:scope_change_id>/review/", ScopeChangeReviewView.as_view(), name="inventory-scope-change-review"),
    # Equipment Returns
    path("equipment-returns/", EquipmentReturnListCreateView.as_view(), name="inventory-equipment-returns"),
    path("equipment-returns/<int:return_id>/", EquipmentReturnDetailView.as_view(), name="inventory-equipment-return-detail"),
    path("equipment-returns/<int:return_id>/receive/", EquipmentReturnReceiveView.as_view(), name="inventory-equipment-return-receive"),
    # Operations Assignment (singleton)
    path("sites/<int:site_id>/operations-assignment/", OperationsAssignmentView.as_view(), name="inventory-operations-assignment"),
    # Elevator Rental (singleton)
    path("sites/<int:site_id>/elevator-rental/", ElevatorRentalView.as_view(), name="inventory-elevator-rental"),
]
