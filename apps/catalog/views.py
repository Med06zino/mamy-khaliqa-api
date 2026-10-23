from django.db.models import Case, Count, F, IntegerField, Q, Sum, When
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsStaffUser

from .filters import ProductFilter
from .models import Category, Product, ProductImage, ProductVariant
from .serializers import (
    AdminCategorySerializer, AdminProductSerializer, AdminVariantSerializer, CategorySerializer,
    ProductDetailSerializer, ProductImageSerializer, ProductListSerializer,
)


def with_availability(qs):
    return qs.annotate(
        _vcount=Count("variants", filter=Q(variants__is_active=True), distinct=True),
        _vstock=Sum("variants__stock", filter=Q(variants__is_active=True)),
    ).annotate(
        avail=Case(When(_vcount__gt=0, then=F("_vstock")), default=F("stock"), output_field=IntegerField())
    )


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    pagination_class = None


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "short_description", "sku"]
    ordering_fields = ["price", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Product.objects.public().select_related("category").prefetch_related("images", "variants")
        return with_availability(qs)

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    @action(detail=False, methods=["get"], url_path="best-sellers")
    def best_sellers(self, request):
        """Meilleures ventes calculees a partir des commandes non annulees. Vide s'il n'y a aucune vente.

        On construit un queryset propre (sans with_availability) pour eviter les conflits
        entre les annotations Count/Sum de with_availability et le Sum sur orderitem__quantity.
        La disponibilite est ensuite calculee via la property Python, ce qui est acceptable
        car le nombre de best-sellers est limite a 8.
        """
        base_qs = (
            Product.objects.public()
            .select_related("category")
            .prefetch_related("images", "variants")
            .exclude(orderitem__order__status="cancelled")
            .annotate(sold=Sum("orderitem__quantity"))
            .filter(sold__gt=0)
            .order_by("-sold")[:8]
        )
        # Re-annoter avec with_availability pour que le serializer puisse utiliser obj.avail.
        pks = [p.pk for p in base_qs]
        if not pks:
            return Response([])
        qs = with_availability(
            Product.objects.public()
            .select_related("category")
            .prefetch_related("images", "variants")
            .filter(pk__in=pks)
            .annotate(sold=Sum("orderitem__quantity"))
            .exclude(orderitem__order__status="cancelled")
        ).order_by("-sold")
        return Response(ProductListSerializer(qs, many=True, context=self.get_serializer_context()).data)


# ---------------- Admin ----------------
class AdminCategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = AdminCategorySerializer
    permission_classes = [IsStaffUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.products.exists():
            return Response(
                {"detail": "Cette categorie contient des produits. Desactivez-la plutot que de la supprimer.", "errors": {}},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class AdminProductViewSet(viewsets.ModelViewSet):
    serializer_class = AdminProductSerializer
    permission_classes = [IsStaffUser]
    search_fields = ["name", "sku"]
    filterset_fields = ["category", "is_published", "is_archived"]
    ordering_fields = ["created_at", "price", "name"]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("images", "variants")

    def destroy(self, request, *args, **kwargs):
        """Archive si le produit figure dans des commandes, sinon supprime."""
        product = self.get_object()
        if product.orderitem_set.exists():
            product.is_archived = True
            product.is_published = False
            product.save(update_fields=["is_archived", "is_published"])
            return Response({"detail": "Produit archive (il figure dans des commandes).", "archived": True})
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def images(self, request, pk=None):
        product = self.get_object()
        file = request.FILES.get("image")
        if not file:
            raise ValidationError({"image": "Fichier manquant."})
        obj = ProductImage(product=product, image=file, alt=request.data.get("alt", product.name))
        try:
            obj.full_clean()
        except Exception as exc:
            raise ValidationError({"image": getattr(exc, "messages", [str(exc)])})
        obj.position = product.images.count()
        obj.save()
        return Response(ProductImageSerializer(obj, context={"request": request}).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        product.images.filter(pk=image_id).delete()
        return Response(status=204)


class AdminVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.select_related("product")
    serializer_class = AdminVariantSerializer
    permission_classes = [IsStaffUser]
    filterset_fields = ["product"]
    pagination_class = None
