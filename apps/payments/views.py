import logging

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from .models import SasPayCheckoutSession, WaveCheckoutSession
from .serializers import SasPayCheckoutSessionDetailSerializer
from .services import (
    create_saspay_checkout_session,
    create_wave_checkout_session,
    process_saspay_webhook,
    simulate_wave_payment,
    verify_saspay_payment,
)

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.GenericViewSet):
    """ViewSet principal pour gérer tous les paiements (Wave, SasPay, etc.)."""

    permission_classes = [IsAuthenticated]
    lookup_field = "number"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="wave/create")
    def create_wave_checkout(self, request, number=None):
        """Crée une session de paiement Wave pour une commande."""
        order = self.get_object()

        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValidationError({"order": "Cette commande est déjà payée."})

        if hasattr(order, "wave_session"):
            session = order.wave_session
            if session.status == WaveCheckoutSession.Status.PENDING:
                return Response({"checkout_url": session.checkout_url, "session_id": session.session_id})
            elif session.status == WaveCheckoutSession.Status.PAID:
                raise ValidationError({"order": "Cette commande est déjà payée via Wave."})

        session = create_wave_checkout_session(order)
        return Response({
            "checkout_url": session.checkout_url,
            "session_id": session.session_id,
            "simulated": True,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="wave/simulate")
    def simulate_wave(self, request):
        """Simule un paiement Wave (uniquement pour les tests)."""
        session_id = request.data.get("session_id")
        success = request.data.get("success", True)

        if not session_id:
            raise ValidationError({"session_id": "session_id est requis"})

        try:
            session = simulate_wave_payment(session_id, success)
            return Response({
                "status": session.status,
                "transaction_id": session.wave_transaction_id,
            })
        except ValidationError as e:
            raise e

    @action(detail=True, methods=["post"], url_path="saspay/create")
    def create_saspay_checkout(self, request, number=None):
        """Crée une session de paiement SasPay pour une commande."""
        order = self.get_object()

        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValidationError({"order": "Cette commande est déjà payée."})

        if hasattr(order, "saspay_session"):
            session = order.saspay_session
            if session.status == SasPayCheckoutSession.Status.PENDING:
                serializer = SasPayCheckoutSessionDetailSerializer(session)
                return Response(serializer.data)
            elif session.status == SasPayCheckoutSession.Status.PAID:
                raise ValidationError({"order": "Cette commande est déjà payée via SasPay."})

        try:
            session = create_saspay_checkout_session(order)
            serializer = SasPayCheckoutSessionDetailSerializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            raise e
        except Exception as e:
            logger.error(f"Error creating SasPay session for order {number}: {str(e)}")
            raise ValidationError(
                {"saspay": "Erreur lors de la création de la session de paiement."}
            )

    @action(detail=True, methods=["get"], url_path="saspay/status")
    def get_saspay_status(self, request, number=None):
        """Récupère le statut du paiement SasPay d'une commande."""
        order = self.get_object()

        if not hasattr(order, "saspay_session"):
            raise ValidationError({"order": "Aucune session SasPay pour cette commande."})

        session = order.saspay_session

        if session.status == SasPayCheckoutSession.Status.PAID:
            serializer = SasPayCheckoutSessionDetailSerializer(session)
            return Response(serializer.data)

        try:
            saspay_data = verify_saspay_payment(session.session_id)

            from .services import _map_saspay_status

            session.status = _map_saspay_status(saspay_data.get("status", "PENDING"))
            if saspay_data.get("transaction"):
                session.saspay_transaction_id = saspay_data["transaction"].get("id")
            session.raw_response = saspay_data
            session.save()

            serializer = SasPayCheckoutSessionDetailSerializer(session)
            return Response(serializer.data)

        except ValidationError as e:
            raise e
        except Exception as e:
            logger.error(f"Error verifying SasPay status for order {number}: {str(e)}")
            raise ValidationError(
                {"saspay": "Erreur lors de la vérification du statut de paiement."}
            )


class SasPayWebhookView(APIView):
    """Endpoint pour recevoir les webhooks de SasPay."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get("X-Webhook-Signature", "")
        timestamp = request.headers.get("X-Webhook-Timestamp", "")
        event_type = request.headers.get("X-Webhook-Event", "")

        if not signature or not timestamp or not event_type:
            logger.warning("Missing required webhook headers")
            return HttpResponse(
                "Missing required headers", status=status.HTTP_400_BAD_REQUEST
            )

        raw_body = request.body

        try:
            process_saspay_webhook(
                raw_body=raw_body,
                signature=signature,
                timestamp=timestamp,
                event_type=event_type,
                payload=request.data,
            )
            return HttpResponse("Webhook processed successfully", status=status.HTTP_200_OK)

        except ValidationError as e:
            logger.warning(f"Webhook validation error: {str(e)}")
            return HttpResponse(
                str(e), status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return HttpResponse(
                "Internal server error", status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
