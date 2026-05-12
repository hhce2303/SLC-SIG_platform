from django.urls import path

from apps.schedules.views import (
    AvailableSlotDeleteView,
    AvailableSlotListCreateView,
    CancellationRequestHandleView,
    CancellationRequestListCreateView,
    NotificationListCreateView,
    NotificationMarkReadView,
    ScheduleBulkUpsertView,
    ScheduleDeleteRangeView,
    ScheduleListView,
    ScheduleUpsertView,
    ShiftTypeListView,
    SlotClaimCreateView,
    SlotClaimDeleteView,
    SlotClaimListView,
    SquadListView,
    SquadToggleEligibilityView,
)

urlpatterns = [
    # Core data
    path("squads/", SquadListView.as_view(), name="sch-squads"),
    path("squads/<int:squad_id>/toggle-eligibility/", SquadToggleEligibilityView.as_view(), name="sch-squad-toggle"),
    path("shift-types/", ShiftTypeListView.as_view(), name="sch-shift-types"),

    # Schedules
    path("schedules/", ScheduleListView.as_view(), name="sch-schedules"),
    path("schedules/upsert/", ScheduleUpsertView.as_view(), name="sch-schedule-upsert"),
    path("schedules/bulk/", ScheduleBulkUpsertView.as_view(), name="sch-schedule-bulk"),
    path("schedules/delete-range/", ScheduleDeleteRangeView.as_view(), name="sch-schedule-delete-range"),

    # Available slots
    path("slots/", AvailableSlotListCreateView.as_view(), name="sch-slots"),
    path("slots/<int:slot_id>/", AvailableSlotDeleteView.as_view(), name="sch-slot-delete"),

    # Slot claims
    path("slot-claims/", SlotClaimListView.as_view(), name="sch-slot-claims"),
    path("slot-claims/claim/", SlotClaimCreateView.as_view(), name="sch-slot-claim-create"),
    path("slot-claims/unclaim/", SlotClaimDeleteView.as_view(), name="sch-slot-claim-delete"),

    # Cancellation requests
    path("cancellation-requests/", CancellationRequestListCreateView.as_view(), name="sch-cancellation-requests"),
    path("cancellation-requests/<int:request_id>/handle/", CancellationRequestHandleView.as_view(), name="sch-cancellation-handle"),

    # Notifications
    path("notifications/", NotificationListCreateView.as_view(), name="sch-notifications"),
    path("notifications/mark-read/", NotificationMarkReadView.as_view(), name="sch-notifications-mark-read"),
]
