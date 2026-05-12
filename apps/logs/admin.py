from django.contrib import admin

from apps.logs.models import DailyEvent


@admin.register(DailyEvent)
class DailyEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_id",
        "site_name",
        "activity_name",
        "event_datetime",
        "event_status",
        "quantity",
    )
    list_filter = ("event_status", "activity")
    search_fields = ("id", "site__site_name", "description")
    list_select_related = ("site", "activity")
    list_per_page = 50
    ordering = ("-event_datetime",)
    readonly_fields = ("id", "event_datetime")

    def site_name(self, obj):
        return obj.site.site_name if obj.site else "-"
    site_name.short_description = "Sitio"

    def activity_name(self, obj):
        return obj.activity.act_name if obj.activity else "-"
    activity_name.short_description = "Actividad"
