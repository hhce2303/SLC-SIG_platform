from django.urls import path

from apps.sigtools.views import SiteDetailView, SiteListView

urlpatterns = [
    path("sites/", SiteListView.as_view(), name="site-list"),
    path("sites/<int:site_id>/", SiteDetailView.as_view(), name="site-detail"),
]
