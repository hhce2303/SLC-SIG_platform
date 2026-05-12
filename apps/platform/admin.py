from django.contrib import admin

from apps.platform.models import Tool, UserToolAccess


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
