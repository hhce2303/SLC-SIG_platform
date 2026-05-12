from django.urls import path

from apps.logs.views import EventListCreateView

urlpatterns = [
    path("", EventListCreateView.as_view(), name="event-list-create"),
]
