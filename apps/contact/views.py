from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.common.permissions import IsStaffUser

from .models import ContactMessage
from .serializers import AdminContactSerializer, ContactMessageSerializer


class ContactViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = ContactMessage.objects.none()
    serializer_class = ContactMessageSerializer
    permission_classes = [AllowAny]
    throttle_scope = "contact"


class AdminContactViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Liste et mise à jour (is_read) des messages de contact pour l'administration.

    La pagination globale (StandardPagination) s'applique.
    Le tri par défaut expose les messages non lus en premier.
    """

    queryset = ContactMessage.objects.all().order_by("is_read", "-created_at")
    serializer_class = AdminContactSerializer
    permission_classes = [IsStaffUser]
    filterset_fields = ["is_read"]
    ordering_fields = ["created_at", "is_read"]
    ordering = ["is_read", "-created_at"]
