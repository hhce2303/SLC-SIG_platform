from django.urls import path
from apps.reports.views import PoliceDispatchListView

urlpatterns = [
    path("police-dispatch/", PoliceDispatchListView.as_view(), name="reports-police-dispatch"),
]
