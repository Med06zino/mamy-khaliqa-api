from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.common.permissions import IsStaffUser

from .filters import ReviewFilter
from .models import Review
from .serializers import AdminReviewSerializer, ReviewSerializer


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Liste publique des avis approuves ; creation reservee aux acheteurs (moderation avant publication)."""

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = ReviewFilter
    # Pas de pagination sur la home (max 3 utilisés) ; conserve la pagination globale sur /reviews/?product=slug
    ordering = ["-created_at"]

    def get_queryset(self):
        return Review.objects.filter(is_approved=True).select_related("user", "product")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, is_approved=False)


class AdminReviewViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Review.objects.select_related("user", "product").order_by("-created_at")
    serializer_class = AdminReviewSerializer
    permission_classes = [IsStaffUser]
    filterset_fields = ["is_approved"]
    # La pagination globale (StandardPagination, page_size=12) s'applique désormais à cet endpoint.
