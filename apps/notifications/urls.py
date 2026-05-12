from django.urls import path

from apps.notifications.views import SpecialMarkView, SupervisorSpecialsListView

urlpatterns = [
    path("specials/supervisor/", SupervisorSpecialsListView.as_view(), name="specials-supervisor-list"),
    path("specials/<int:pk>/mark/", SpecialMarkView.as_view(), name="specials-mark"),
]
