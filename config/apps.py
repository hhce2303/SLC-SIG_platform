from django.contrib.admin.apps import AdminConfig


class DailyLogAdminConfig(AdminConfig):
    """
    Replaces the default Django admin site with DailyLogAdminSite.
    The `name` inherited from AdminConfig stays 'django.contrib.admin'.
    """
    default_site = "config.admin_sites.DailyLogAdminSite"
