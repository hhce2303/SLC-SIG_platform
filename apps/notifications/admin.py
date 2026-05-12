from django.contrib import admin

from apps.notifications.models import News, Special


@admin.register(Special)
class SpecialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_id",
        "user_id",
        "supervisor_id",
        "spec_datetime",
        "spec_status",
        "spec_marked_at",
    )
    list_filter = ("spec_status",)
    search_fields = ("id", "spec_description")
    list_select_related = ("event", "user", "supervisor")
    list_per_page = 50
    ordering = ("-spec_datetime",)
    readonly_fields = ("id", "spec_datetime")


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "news_type",
        "news_urgency",
        "news_datetime_in",
        "news_datetime_out",
        "active",
    )
    list_filter = ("news_type", "news_urgency", "active")
    search_fields = ("news_info",)
    list_per_page = 50
    ordering = ("-news_datetime_in",)
