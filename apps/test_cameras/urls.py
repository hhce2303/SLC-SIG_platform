"""Test Cameras URL routing."""

from django.urls import path

from apps.test_cameras import views

urlpatterns = [
    path("site/<int:site_id>/", views.SiteCamerasListView.as_view(), name="site-cameras-list"),
]
