from django.contrib import admin

from config.admin_sites import schedules_admin
from apps.schedules.models import (
    AppNotification,
    AvailableSlot,
    CancellationRequest,
    Schedule,
    ShiftType,
    SlotClaim,
    Squad,
    SquadPattern,
)


@admin.register(Squad, site=schedules_admin)
class SquadAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color_theme", "is_static", "can_take_slots")
    list_filter = ("is_static", "can_take_slots")
    search_fields = ("name",)


@admin.register(ShiftType, site=schedules_admin)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "start_time", "end_time", "is_off", "is_custom")
    list_filter = ("is_off", "is_custom")
    search_fields = ("name",)


@admin.register(Schedule, site=schedules_admin)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "shift_date", "shift_type_id")
    list_filter = ("shift_date",)
    search_fields = ("user__username",)
    date_hierarchy = "shift_date"


@admin.register(SquadPattern, site=schedules_admin)
class SquadPatternAdmin(admin.ModelAdmin):
    list_display = ("id", "squad", "day_of_week", "shift_type_id")
    list_filter = ("day_of_week",)
    raw_id_fields = ("squad",)


@admin.register(AvailableSlot, site=schedules_admin)
class AvailableSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "slot_date", "shift_type_id", "total_slots", "taken_slots")
    list_filter = ("slot_date",)
    date_hierarchy = "slot_date"


@admin.register(SlotClaim, site=schedules_admin)
class SlotClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "slot", "user_id", "claimed_at")
    raw_id_fields = ("slot",)


@admin.register(CancellationRequest, site=schedules_admin)
class CancellationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "slot", "user_id", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("slot",)


@admin.register(AppNotification, site=schedules_admin)
class AppNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "message_short", "is_global", "target_user_id", "read", "created_at")
    list_filter = ("is_global", "read")
    search_fields = ("message",)

    @admin.display(description="Message")
    def message_short(self, obj: AppNotification) -> str:
        return obj.message[:80] if obj.message else ""
