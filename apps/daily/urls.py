from django.urls import path
from apps.daily.views import PoliceDispatchListView

urlpatterns = [
    path("police-dispatch/", PoliceDispatchListView.as_view(), name="daily-police-dispatch"),
]
