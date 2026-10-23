from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.common.permissions import IsStaffUser

from .models import DeliveryZone
from .serializers import AdminDeliveryZoneSerializer, DeliveryZoneSerializer


class DeliveryZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryZone.objects.filter(is_active=True)
    serializer_class = DeliveryZoneSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class AdminDeliveryZoneViewSet(viewsets.ModelViewSet):
    queryset = DeliveryZone.objects.all()
    serializer_class = AdminDeliveryZoneSerializer
    permission_classes = [IsStaffUser]
    pagination_class = None
