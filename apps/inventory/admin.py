from django.contrib import admin

from config.admin_sites import inventory_admin
from apps.inventory.models import ActivityLog, Article, Group


@admin.register(Group, site=inventory_admin)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color")
    search_fields = ("name",)


@admin.register(Article, site=inventory_admin)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "status", "location", "group")
    list_filter = ("status", "category")
    search_fields = ("sku", "name", "serial")
    raw_id_fields = ("group",)


@admin.register(ActivityLog, site=inventory_admin)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "action", "user_id", "timestamp")
    list_filter = ("action",)
    search_fields = ("article__name", "user_id")

