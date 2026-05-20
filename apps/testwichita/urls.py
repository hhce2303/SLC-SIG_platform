from django.urls import path

from apps.testwichita.views import WichitaCamerasView

urlpatterns = [
    path("", WichitaCamerasView.as_view(), name="testwichita-cameras"),
]
