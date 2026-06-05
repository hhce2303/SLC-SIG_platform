from django.urls import path

from apps.installations import views

app_name = "installations"

urlpatterns = [
    # --- Catalog ---
    path("catalog/cameras/", views.CameraCatalogView.as_view(), name="catalog-cameras"),
    path("catalog/camera-models/", views.CameraModelCatalogView.as_view(), name="catalog-camera-models"),
    path("catalog/devices/", views.DeviceCatalogView.as_view(), name="catalog-devices"),
    path("catalog/vms/", views.VMSCatalogView.as_view(), name="catalog-vms"),
    path("catalog/installation-types/", views.InstallationTypesCatalogView.as_view(), name="catalog-installation-types"),

    # --- Customer groups ---
    path("customer-groups/", views.CustomerGroupsView.as_view(), name="customer-groups"),

    # --- Users ---
    path("users/", views.UsersView.as_view(), {"role": "it-technicians"}, name="users-default"),
    path("users/admins/", views.UsersView.as_view(), {"role": "admins"}, name="users-admins"),
    path("users/project-owners/", views.UsersView.as_view(), {"role": "project-owners"}, name="users-project-owners"),
    path("users/it-technicians/", views.UsersView.as_view(), {"role": "it-technicians"}, name="users-it-technicians"),
    path("users/lead-techs/", views.UsersView.as_view(), {"role": "lead-techs"}, name="users-lead-techs"),
    path("users/developers/", views.UsersView.as_view(), {"role": "developers"}, name="users-developers"),

    # --- Sites ---
    path("sites/", views.SiteListView.as_view(), name="site-list"),
    path("sites/dispatch-progress/", views.SitesDispatchProgressView.as_view(), name="sites-dispatch-progress"),
    path("onboarding/", views.SiteOnboardingView.as_view(), name="site-onboarding"),
    path("project-sites/", views.ProjectSiteListView.as_view(), name="project-site-list"),
    path("sites/<int:site_id>/info/", views.ProjectSiteInfoView.as_view(), name="project-site-info"),
    path("sites/<int:site_id>/it-test/", views.ItSiteTestView.as_view(), name="site-it-test"),
    path("sites/<int:site_id>/", views.SiteDetailView.as_view(), name="site-detail"),
    path("sites/<int:site_id>/status/", views.SiteStatusView.as_view(), name="site-status"),
    path("sites/<int:site_id>/inventory/", views.SiteInventoryView.as_view(), name="site-inventory"),
    path("sites/<int:site_id>/catalog/", views.SiteDeviceCatalogView.as_view(), name="site-device-catalog"),
    path("sites/<int:site_id>/topology/validate/", views.SiteTopologyValidateView.as_view(), name="site-topology-validate"),
    path("sites/<int:site_id>/bom/", views.SiteBOMView.as_view(), name="site-bom"),
    path("sites/<int:site_id>/indoor-maps/", views.SiteIndoorMapView.as_view(), name="site-indoor-maps"),
    path("sites/<int:site_id>/indoor-maps/<int:map_id>/", views.SiteIndoorMapDetailView.as_view(), name="site-indoor-map-detail"),

    # --- Projects (Installations) ---
    path("projects/", views.ProjectListView.as_view(), name="project-list"),
    path("projects/<int:inst_id>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:inst_id>/design/", views.ProjectDesignView.as_view(), name="project-design"),
    path("projects/<int:inst_id>/sync/", views.ProjectSyncView.as_view(), name="project-sync"),
    path("projects/<int:inst_id>/inventory/", views.ProjectInventoryView.as_view(), name="project-inventory"),
    path("projects/<int:inst_id>/devices/bulk-parent/", views.BulkDeviceParentView.as_view(), name="project-bulk-parent"),

    # --- Devices ---
    path("devices/positions/", views.DevicePositionsView.as_view(), name="device-positions"),
    path("devices/<int:item_id>/", views.DeviceDetailView.as_view(), name="device-detail"),
    path("devices/<int:device_id>/parent/", views.DeviceParentView.as_view(), name="device-parent"),

    # --- Sig Projects (sig_projects — default DB) ---
    path("sig-projects/", views.SigProjectListView.as_view(), name="sig-project-list"),
    path("sig-projects/<uuid:project_id>/", views.SigProjectDetailView.as_view(), name="sig-project-detail"),
    path("sig-projects/<uuid:project_id>/name/", views.SigProjectRenameView.as_view(), name="sig-project-rename"),
    path("sig-projects/<uuid:project_id>/request-approval/", views.SigProjectRequestApprovalView.as_view(), name="sig-project-request-approval"),
    path("sig-projects/<uuid:project_id>/cancel-approval-request/", views.SigProjectCancelApprovalView.as_view(), name="sig-project-cancel-approval-request"),

    # --- Admin (sigtools_beta) ---
    path("admin/users/", views.AdminUsersView.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", views.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/roles/", views.AdminRolesView.as_view(), name="admin-roles"),
    path("admin/roles/<int:role_id>/", views.AdminRoleDetailView.as_view(), name="admin-role-detail"),
    path("admin/permissions/", views.AdminPermissionsView.as_view(), name="admin-permissions"),

    # --- Dispatch / Receipt / Installation ---
    path("sites/<int:site_id>/catalog/<str:device_id>/",         views.SiteDeviceDispatchView.as_view(),  name="site-device-dispatch"),
    path("sites/<int:site_id>/catalog/<str:device_id>/receive/", views.SiteDeviceReceiveView.as_view(),   name="site-device-receive"),
    path("sites/<int:site_id>/catalog/<str:device_id>/install/", views.SiteDeviceInstallView.as_view(),   name="site-device-install"),
    path("sites/<int:site_id>/catalog/<str:device_id>/serial/",  views.SiteDeviceSerialView.as_view(),    name="site-device-serial"),
    path("sites/<int:site_id>/catalog/<str:device_id>/logs/",    views.SiteDeviceLogsView.as_view(),      name="site-device-logs"),
    path("sites/<int:site_id>/progress/",                        views.SiteProgressView.as_view(),        name="site-progress"),

    # --- Real-time SSE (async, Redis pub/sub) ---
    path("stream/", views.installations_sse_stream, name="installations-sse-stream"),
    path("projects/stream/", views.projects_sse_stream, name="projects-sse-stream"),

    # --- Dashboard init (unified first-load payload) ---
    path("dashboard-init/", views.DashboardInitView.as_view(), name="dashboard-init"),

    # --- Metrics / analytics ---
    path("metrics/ceo-dashboard/", views.CeoDashboardView.as_view(), name="metrics-ceo-dashboard"),

    # --- Inventory export (canvas → DB) ---
    path("inventory/export/", views.InventoryExportView.as_view(), name="inventory-export"),

    # --- In-app notifications ---
    path("notifications/", views.NotificationListView.as_view(), name="notification-list"),
    path("notifications/read-all/", views.NotificationMarkAllReadView.as_view(), name="notification-read-all"),
    path("notifications/<int:pk>/read/", views.NotificationMarkReadView.as_view(), name="notification-read"),
]
