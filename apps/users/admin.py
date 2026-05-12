from django.contrib import admin
from django.utils import timezone

from apps.core.models import StationMap
from apps.users.models import Break, CoverCompleted, CoverRequest, Session


@admin.action(description="Desactivar sesiones seleccionadas (logout forzado)")
def force_deactivate(modeladmin, request, queryset):
    """Close selected sessions and free their stations."""
    now = timezone.now()
    user_ids = list(queryset.values_list("user_id", flat=True))

    queryset.update(sesion_active=0, sesion_out=now)

    # Free stations occupied by those users
    StationMap.objects.filter(station_user_id__in=user_ids).update(
        station_user_id=None,
    )

    modeladmin.message_user(
        request,
        f"{len(user_ids)} sesión(es) desactivada(s) y estaciones liberadas.",
    )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_id",
        "user_name",
        "station_id",
        "sesion_in",
        "sesion_out",
        "sesion_active",
        "sesion_status",
        "status_label",
    )
    list_filter = ("sesion_active", "sesion_status")
    search_fields = ("user__profile__user_name", "user__pk")
    list_per_page = 50
    ordering = ("-sesion_in",)
    actions = [force_deactivate]

    list_display_links = ("id",)
    readonly_fields = ("id", "user_id", "station_id", "sesion_in")

    def user_name(self, obj):
        try:
            return obj.user.profile.user_name
        except Exception:
            return f"User #{obj.user_id}"
    user_name.short_description = "Usuario"

    def status_label(self, obj):
        labels = {0: "Offline", 1: "Active", 2: "Available"}
        return labels.get(obj.sesion_status, obj.sesion_status)
    status_label.short_description = "Status"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user__profile", "station")
        )


@admin.register(CoverRequest)
class CoverRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "station_id", "cover_time_request", "approved", "active")
    list_filter = ("approved", "active")
    search_fields = ("user__profile__user_name",)
    list_select_related = ("user", "station")
    list_per_page = 50
    ordering = ("-cover_time_request",)


@admin.register(CoverCompleted)
class CoverCompletedAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "cover_by_id", "cover_in", "cover_out")
    search_fields = ("user__profile__user_name",)
    list_select_related = ("user", "cover_by")
    list_per_page = 50
    ordering = ("-cover_in",)


@admin.register(Break)
class BreakAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_covered_id",
        "user_covering_id",
        "supervisor_id",
        "break_datetime",
        "active",
    )
    list_filter = ("active",)
    search_fields = ("user_covered__profile__user_name", "user_covering__profile__user_name")
    list_select_related = ("user_covered", "user_covering", "supervisor")
    list_per_page = 50
    ordering = ("-break_datetime",)
