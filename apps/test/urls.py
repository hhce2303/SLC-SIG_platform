from django.urls import path
from apps.test.views import CameraListView

urlpatterns = [
    path('cameras/', CameraListView.as_view(), name='camera-list'),
]
