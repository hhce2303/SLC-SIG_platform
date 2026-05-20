from django.urls import path

from apps.layers import views

urlpatterns = [
    path("", views.LayerListView.as_view(), name="layers-list"),
]
