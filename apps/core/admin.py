from django.contrib import admin

from apps.core.models import (
    Activity,
    Site,
    SpecialGroup,
    StationInfo,
    StationMap,
    User,
    UserName,
    UserRole,
)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "role")
    list_filter = ("role",)
    search_fields = ("id", "profile__user_name")
    list_select_related = ("role", "profile")

    def display_name(self, obj):
        try:
            return obj.profile.user_name
        except Exception:
            return f"User #{obj.pk}"
    display_name.short_description = "Nombre"


@admin.register(UserName)
class UserNameAdmin(admin.ModelAdmin):
    list_display = ("user_id", "user_name")
    search_fields = ("user_name",)


@admin.register(StationInfo)
class StationInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "station_number")
    search_fields = ("station_number",)


@admin.register(StationMap)
class StationMapAdmin(admin.ModelAdmin):
    list_display = ("station_id", "station_user_id", "is_active")
    list_filter = ("is_active",)
    list_select_related = ("station", "station_user")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("id", "site_name", "group_id", "site_timezone")
    list_filter = ("group_id",)
    search_fields = ("site_name", "group_id")
    list_per_page = 50


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "act_name")
    search_fields = ("act_name",)


@admin.register(SpecialGroup)
class SpecialGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "group_code")
    search_fields = ("group_code",)
