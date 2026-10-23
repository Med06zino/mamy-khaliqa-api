from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, Payment


class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "first_name", "last_name", "status", "payment_status", "total", "created_at"]
    list_filter = ["status", "payment_status", "source"]
    search_fields = ["number", "phone", "email"]
    inlines = [ItemInline]


admin.site.register(OrderStatusHistory)
admin.site.register(Payment)
