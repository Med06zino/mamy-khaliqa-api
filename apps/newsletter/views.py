from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.permissions import IsStaffUser

from .models import NewsletterSubscriber
from .serializers import AdminNewsletterSerializer, SubscribeSerializer


class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/

    Règle métier :
    - Si l'e-mail est déjà abonné et actif  → réponse 200, pas de doublon.
    - Si l'e-mail est connu mais désactivé  → réactivation, réponse 200.
    - Si l'e-mail est nouveau               → création, réponse 201.
    - Même réponse dans tous les cas pour éviter l'énumération d'adresses.
    """

    permission_classes = [AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "newsletter"

    def post(self, request):
        s = SubscribeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"]

        obj, created = NewsletterSubscriber.objects.get_or_create(email=email)
        if not created and not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active"])

        return Response(
            {"detail": "Merci ! Vous êtes maintenant abonné(e) à notre communauté."},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminNewsletterViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Liste et gestion des abonnés depuis l'administration.

    Permet à l'admin de désactiver des abonnés sans les supprimer.
    """

    queryset = NewsletterSubscriber.objects.all()
    serializer_class = AdminNewsletterSerializer
    permission_classes = [IsStaffUser]
    search_fields = ["email"]
    ordering = ["-subscribed_at"]
    filterset_fields = ["is_active"]
