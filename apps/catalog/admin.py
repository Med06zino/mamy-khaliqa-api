from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductImage, ProductVariant, StockMovement


# ─── Inlines ──────────────────────────────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 10
    fields = ["image", "alt", "position", "preview"]
    readonly_fields = ["preview"]

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;width:60px;object-fit:cover;border-radius:6px;" />',
                obj.image.url,
            )
        return "—"
    preview.short_description = "Aperçu"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ["name", "sku", "price", "stock", "is_active"]


# ─── Category ─────────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ["name", "slug", "product_count_display", "is_active", "position"]
    list_editable = ["is_active", "position"]
    list_filter   = ["is_active"]
    search_fields = ["name"]
    ordering      = ["position", "name"]
    prepopulated_fields = {}   # slug auto-généré par le modèle, on laisse Django faire

    def has_add_permission(self, request):
        """Empêche la création de nouvelles catégories"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression des catégories principales"""
        if obj and obj.slug in ["khaliqa-beauty", "khaliqa-hair"]:
            return False
        return True

    def get_readonly_fields(self, request, obj=None):
        """Rend le slug readonly pour les catégories principales"""
        if obj and obj.slug in ["khaliqa-beauty", "khaliqa-hair"]:
            return ["slug", "name"]
        return []

    def product_count_display(self, obj):
        return Product.objects.filter(category=obj, is_published=True, is_archived=False).count()
    product_count_display.short_description = "Produits publiés"


# ─── Product ──────────────────────────────────────────────────────────────────

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # ── Liste ──────────────────────────────────────────────────────────────────
    list_display  = [
        "thumbnail", "name", "category_badge", "price_display",
        "stock_display", "is_published", "is_featured", "is_archived",
    ]
    list_editable = ["is_published", "is_featured"]
    list_filter   = ["category", "is_published", "is_featured", "is_archived"]
    search_fields = ["name", "sku", "short_description"]
    list_per_page = 25
    ordering      = ["-created_at"]
    date_hierarchy = "created_at"

    # ── Formulaire ─────────────────────────────────────────────────────────────
    fieldsets = (
        ("Informations principales", {
            "fields": ("category", "name", "sku", "volume", "short_description"),
        }),
        ("Prix", {
            "fields": ("price", "compare_at_price"),
            "description": (
                "Le prix est en FCFA. "
                "Renseigner <strong>Ancien prix</strong> uniquement s'il s'agit d'une vraie promotion."
            ),
        }),
        ("Stock", {
            "fields": ("stock",),
            "description": "Ce stock est utilisé uniquement si le produit n'a PAS de variantes.",
        }),
        ("Contenu produit", {
            "fields": ("description", "ingredients", "usage_tips", "precautions"),
            "classes": ("collapse",),
        }),
        ("Publication", {
            "fields": ("is_published", "is_featured", "is_archived"),
            "description": (
                "<strong>Publié</strong> : visible sur le site. "
                "<strong>Mis en avant</strong> : apparaît en page d'accueil. "
                "<strong>Archivé</strong> : masqué sans suppression."
            ),
        }),
    )
    inlines = [ProductImageInline, ProductVariantInline]
    readonly_fields = ["created_at", "updated_at"]

    # ── Vignette dans la liste ─────────────────────────────────────────────────
    def thumbnail(self, obj):
        img = obj.images.first()
        if img:
            return format_html(
                '<img src="{}" style="height:48px;width:48px;object-fit:cover;'
                'border-radius:8px;border:1px solid #ddd;" />',
                img.image.url,
            )
        return format_html('<span style="color:#999;font-size:12px;">Aucune image</span>')
    thumbnail.short_description = "Photo"

    def category_badge(self, obj):
        colors = {
            "beauty":   "#713F52",
            "beaute":   "#713F52",
            "hair":     "#C6A36A",
            "capillair":"#C6A36A",
            "cheveux":  "#C6A36A",
            "cils":     "#C6A36A",
        }
        slug = obj.category.slug.lower()
        color = next((v for k, v in colors.items() if k in slug), "#666")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color,
            obj.category.name,
        )
    category_badge.short_description = "Gamme"

    def price_display(self, obj):
        txt = f"{obj.price:,} FCFA".replace(",", " ")
        if obj.compare_at_price:
            old = f"{obj.compare_at_price:,} FCFA".replace(",", " ")
            return format_html(
                '<strong style="color:#713F52;">{}</strong> '
                '<s style="color:#999;font-size:11px;">{}</s>',
                txt, old,
            )
        return format_html('<strong style="color:#713F52;">{}</strong>', txt)
    price_display.short_description = "Prix"

    def stock_display(self, obj):
        qty = obj.available_stock
        if qty <= 0:
            color, label = "#c0392b", "Rupture"
        elif qty <= 5:
            color, label = "#e67e22", f"{qty} restant{'s' if qty > 1 else ''}"
        else:
            color, label = "#27ae60", f"{qty} en stock"
        return format_html('<span style="color:{};">{}</span>', color, label)
    stock_display.short_description = "Stock"


# ─── StockMovement ────────────────────────────────────────────────────────────

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["created_at", "product", "variant", "delta", "reason", "reference"]
    list_filter  = ["reason"]
    search_fields = ["product__name", "reference"]
    readonly_fields = ["created_at", "product", "variant", "delta", "reason", "reference"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False  # les mouvements sont créés par le code, pas manuellement


# ─── Personnalisation du site admin ───────────────────────────────────────────

admin.site.site_header = "Mamy Khaliqa — Administration"
admin.site.site_title  = "Mamy Khaliqa"
admin.site.index_title = "Tableau de bord"
