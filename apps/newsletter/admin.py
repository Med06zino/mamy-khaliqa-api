from django.contrib import admin

from .models import NewsletterSubscriber


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display  = ["email", "is_active", "subscribed_at"]
    list_filter   = ["is_active"]
    search_fields = ["email"]
    readonly_fields = ["email", "subscribed_at"]
    ordering      = ["-subscribed_at"]
    actions       = ["deactivate_selected"]

    @admin.action(description="Désactiver les abonnés sélectionnés")
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
