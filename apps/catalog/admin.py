from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant, StockMovement


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "stock", "is_published", "is_archived"]
    list_filter = ["category", "is_published", "is_archived"]
    search_fields = ["name", "sku"]
    inlines = [ImageInline, VariantInline]


admin.site.register(Category)
admin.site.register(StockMovement)
