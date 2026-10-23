from django.db import transaction
from django.db.models import Avg
from rest_framework import serializers

from .models import Category, Product, ProductImage, ProductVariant, StockMovement


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "image", "product_count"]

    def get_product_count(self, obj):
        return Product.objects.public().filter(category=obj).count()


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt", "position"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class VariantSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ["id", "name", "sku", "price", "stock"]

    def get_price(self, obj):
        return obj.effective_price


def stock_status(qty, threshold):
    if qty <= 0:
        return "out_of_stock"
    return "low_stock" if qty <= threshold else "in_stock"


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    has_variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "sku", "price", "compare_at_price", "volume", "short_description",
            "category", "main_image", "available_stock", "stock_status", "has_variants", "created_at",
        ]

    def _threshold(self):
        from apps.store_settings.models import StoreSettings

        ctx = self.context
        if "threshold" not in ctx:
            ctx["threshold"] = StoreSettings.load().low_stock_threshold
        return ctx["threshold"]

    def get_category(self, obj):
        return {"id": obj.category_id, "name": obj.category.name, "slug": obj.category.slug}

    def get_main_image(self, obj):
        img = next(iter(obj.images.all()), None)
        if not img:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(img.image.url) if request else img.image.url

    def get_available_stock(self, obj):
        # Utilise l'annotation SQL 'avail' injectée par with_availability() pour éviter le N+1.
        # Fallback sur la property Python si l'objet vient d'une queryset non annotée (admin, tests).
        if hasattr(obj, "avail") and obj.avail is not None:
            return obj.avail
        return obj.available_stock

    def get_stock_status(self, obj):
        qty = self.get_available_stock(obj)
        return stock_status(qty, self._threshold())

    def get_has_variants(self, obj):
        return obj.has_variants


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    user_can_review = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description", "ingredients", "usage_tips", "precautions", "images", "variants", "related",
            "rating", "user_can_review",
        ]

    def get_variants(self, obj):
        return VariantSerializer(obj.variants.filter(is_active=True), many=True).data

    def get_related(self, obj):
        qs = (
            Product.objects.public()
            .filter(category=obj.category)
            .exclude(pk=obj.pk)
            .select_related("category")
            .prefetch_related("images")[:4]
        )
        return ProductListSerializer(qs, many=True, context=self.context).data

    def get_rating(self, obj):
        agg = obj.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"))
        count = obj.reviews.filter(is_approved=True).count()
        return {"average": round(agg["avg"], 1) if agg["avg"] else None, "count": count}

    def get_user_can_review(self, obj):
        from apps.reviews.serializers import user_can_review

        request = self.context.get("request")
        return user_can_review(getattr(request, "user", None), obj)


# ---------------- Admin ----------------
class AdminVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "product", "name", "sku", "price", "stock", "is_active"]

    def update(self, instance, validated):
        old = instance.stock
        inst = super().update(instance, validated)
        if inst.stock != old:
            StockMovement.objects.create(
                product=inst.product, variant=inst, delta=inst.stock - old, reason=StockMovement.Reason.ADJUST
            )
        return inst


class AdminProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = AdminVariantSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "category_name", "name", "slug", "sku", "short_description", "description",
            "price", "compare_at_price", "stock", "available_stock", "volume", "ingredients", "usage_tips",
            "precautions", "is_published", "is_archived", "created_at", "images", "variants",
        ]
        read_only_fields = ["slug", "created_at"]

    def validate(self, data):
        price = data.get("price", getattr(self.instance, "price", None))
        promo = data.get("compare_at_price", getattr(self.instance, "compare_at_price", None))
        if promo is not None and price is not None and promo <= price:
            raise serializers.ValidationError(
                {"compare_at_price": "L'ancien prix doit etre superieur au prix actuel."}
            )
        return data

    @transaction.atomic
    def update(self, instance, validated):
        old = instance.stock
        inst = super().update(instance, validated)
        if inst.stock != old:
            StockMovement.objects.create(
                product=inst, delta=inst.stock - old, reason=StockMovement.Reason.ADJUST
            )
        return inst


class AdminCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "image", "is_active", "position"]
        read_only_fields = ["slug"]
