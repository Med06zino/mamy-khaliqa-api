from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny

from apps.common.permissions import IsStaffUser

from .models import Banner
from .serializers import AdminBannerSerializer, BannerSerializer


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    """Bannières actives, publiques, filtrables par type.

    GET /api/v1/banners/           → toutes les bannières actives
    GET /api/v1/banners/?type=hero → uniquement les hero
    GET /api/v1/banners/?type=promo → uniquement les promotionnelles
    """

    serializer_class = BannerSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filterset_fields = ["banner_type"]

    def get_queryset(self):
        return Banner.objects.filter(is_active=True).order_by("position", "id")


class AdminBannerViewSet(viewsets.ModelViewSet):
    """CRUD bannières pour l'administration."""

    queryset = Banner.objects.all().order_by("position", "id")
    serializer_class = AdminBannerSerializer
    permission_classes = [IsStaffUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["banner_type", "is_active"]
