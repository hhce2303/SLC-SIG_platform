from django.urls import path

from apps.core.views import ActivityListView, SiteListView

urlpatterns = [
    path("sites/", SiteListView.as_view(), name="catalog-sites"),
    path("activities/", ActivityListView.as_view(), name="catalog-activities"),
]
