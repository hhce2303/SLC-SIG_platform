from django.contrib import admin
from django.core.cache import cache

from apps.platform.models import DailyTokenEpoch, Tool, UserToolAccess
from apps.users.authentication import token_epoch_cache_key


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "frontend_url", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("slug", "name")
    ordering = ("order", "name")
    prepopulated_fields = {"slug": ("name",)}


class UserToolAccessInline(admin.TabularInline):
    model = UserToolAccess
    extra = 1
    fields = ("tool", "is_active", "granted_at")
    readonly_fields = ("granted_at",)


@admin.register(UserToolAccess)
class UserToolAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "tool", "is_active", "granted_at")
    list_filter = ("tool", "is_active")
    search_fields = ("user__username",)
    ordering = ("user", "tool__order")


@admin.register(DailyTokenEpoch)
class DailyTokenEpochAdmin(admin.ModelAdmin):
    """
    Revoke every outstanding JWT for an operator (ADR-0001 point 7) by
    creating/editing a row here with `revoked_since` set to now (or any
    timestamp -- every token issued at or before it is rejected). Deleting
    the row un-revokes.

    save_model()/delete_model() invalidate the same Redis key
    DailyJWTAuthentication reads (60s TTL cache-aside), so a revocation
    made here takes effect immediately instead of waiting out the cache
    window -- this is the write-side half of the "instant revocation"
    contract; without it, a just-revoked token would still work for up to
    60s.
    """

    list_display = ("daily_user_id", "revoked_since")
    ordering = ("-revoked_since",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete(token_epoch_cache_key(obj.daily_user_id))

    def delete_model(self, request, obj):
        daily_user_id = obj.daily_user_id
        super().delete_model(request, obj)
        cache.delete(token_epoch_cache_key(daily_user_id))

    def delete_queryset(self, request, queryset):
        ids = list(queryset.values_list("daily_user_id", flat=True))
        super().delete_queryset(request, queryset)
        for daily_user_id in ids:
            cache.delete(token_epoch_cache_key(daily_user_id))
