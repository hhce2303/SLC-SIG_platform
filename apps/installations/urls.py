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
    path("onboarding/", views.SiteOnboardingView.as_view(), name="site-onboarding"),
    path("sites/<int:site_id>/", views.SiteDetailView.as_view(), name="site-detail"),
    path("sites/<int:site_id>/status/", views.SiteStatusView.as_view(), name="site-status"),
    path("sites/<int:site_id>/inventory/", views.SiteInventoryView.as_view(), name="site-inventory"),
    path("sites/<int:site_id>/catalog/", views.SiteDeviceCatalogView.as_view(), name="site-device-catalog"),

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

    # --- Admin (sigtools_beta) ---
    path("admin/users/", views.AdminUsersView.as_view(), name="admin-users"),
    path("admin/users/<int:user_id>/", views.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/roles/", views.AdminRolesView.as_view(), name="admin-roles"),
    path("admin/roles/<uuid:role_id>/", views.AdminRoleDetailView.as_view(), name="admin-role-detail"),
    path("admin/permissions/", views.AdminPermissionsView.as_view(), name="admin-permissions"),
]
