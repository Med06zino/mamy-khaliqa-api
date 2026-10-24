from django.contrib import admin

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display  = ["title", "banner_type", "position", "is_active", "created_at"]
    list_editable = ["position", "is_active"]
    list_filter   = ["banner_type", "is_active"]
    ordering      = ["position", "id"]
