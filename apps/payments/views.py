import json
import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from .models import SasPayCheckoutSession, WaveCheckoutSession
from .serializers import SasPayCheckoutSessionSerializer, WaveCheckoutSessionSerializer
from .services import (
    create_saspay_checkout_session,
    create_wave_checkout_session,
    process_saspay_webhook,
    process_wave_webhook,
    simulate_wave_payment,
)

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.GenericViewSet):
    """Endpoints de gestion des paiements client (Wave & SasPay)."""

    permission_classes = [AllowAny]
    lookup_field = "number"

    def get_object(self):
        number = self.kwargs.get("number")
        order = get_object_or_404(Order, number=number)
        # Sécurité : si la commande appartient à un utilisateur connecté, seul lui peut y accéder
        if order.user and self.request.user.is_authenticated and order.user != self.request.user:
            raise PermissionDenied("Vous n'êtes pas autorisé à accéder à cette commande.")
        return order

    @action(detail=True, methods=["get"], url_path="status")
    def get_payment_status(self, request, number=None):
        """Consulte l'état global du paiement pour une commande (Wave, SasPay, etc.)."""
        order = self.get_object()
        provider = order.payment_method or "unknown"
        status_value = "unpaid"
        if order.payment_status == Order.PaymentStatus.PAID:
            status_value = "paid"
        elif hasattr(order, "wave_session"):
            status_value = order.wave_session.status
            provider = "wave"
        elif hasattr(order, "saspay_session"):
            status_value = order.saspay_session.status
            provider = "saspay"

        return Response({
            "order_number": order.number,
            "payment_status": order.payment_status,
            "status": status_value,
            "payment_method": provider,
            "total": order.total,
        })

    # ── Wave Senegal ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="wave/create")
    def create_wave_checkout(self, request, number=None):
        """Initialise une session de paiement Wave pour la commande."""
        order = self.get_object()

        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValidationError({"order": "Cette commande est déjà payée."})

        # Si une session en attente existe déjà, la renvoyer
        if hasattr(order, "wave_session") and order.wave_session.status == WaveCheckoutSession.Status.PENDING:
            serializer = WaveCheckoutSessionSerializer(order.wave_session)
            return Response(serializer.data)

        session = create_wave_checkout_session(order)
        serializer = WaveCheckoutSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="wave/status")
    def get_wave_status(self, request, number=None):
        """Consulte l'état du paiement Wave pour une commande."""
        order = self.get_object()
        if not hasattr(order, "wave_session"):
            raise ValidationError({"order": "Aucune session Wave initiée pour cette commande."})
        serializer = WaveCheckoutSessionSerializer(order.wave_session)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="wave/simulate")
    def simulate_wave(self, request):
        """Endpoint de simulation pour les tests en développement local."""
        session_id = request.data.get("session_id")
        success = request.data.get("success", True)
        if not session_id:
            raise ValidationError({"session_id": "L'identifiant session_id est obligatoire."})

        session = simulate_wave_payment(session_id, success=success)
        return Response({
            "status": session.status,
            "order_number": session.order.number,
            "transaction_id": session.wave_transaction_id,
        })

    # ── Passerelle SasPay ────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="saspay/create")
    def create_saspay_checkout(self, request, number=None):
        """Initialise une session de paiement SasPay pour la commande."""
        order = self.get_object()

        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValidationError({"order": "Cette commande est déjà payée."})

        if hasattr(order, "saspay_session") and order.saspay_session.status == SasPayCheckoutSession.Status.PENDING:
            serializer = SasPayCheckoutSessionSerializer(order.saspay_session)
            return Response(serializer.data)

        session = create_saspay_checkout_session(order)
        serializer = SasPayCheckoutSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="saspay/status")
    def get_saspay_status(self, request, number=None):
        """Consulte l'état du paiement SasPay pour une commande."""
        order = self.get_object()
        if not hasattr(order, "saspay_session"):
            raise ValidationError({"order": "Aucune session SasPay initiée pour cette commande."})
        serializer = SasPayCheckoutSessionSerializer(order.saspay_session)
        return Response(serializer.data)


class WaveWebhookView(APIView):
    """Endpoint Webhook Wave officiel (POST https://api.votresite.com/api/v1/payments/wave/webhook/)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature_header = request.headers.get("Wave-Signature", "")
        if not signature_header:
            logger.warning("Webhook Wave reçu sans header Wave-Signature.")
            return HttpResponse("Missing Wave-Signature header", status=status.HTTP_400_BAD_REQUEST)

        raw_body = request.body
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = request.data

        try:
            process_wave_webhook(raw_body, signature_header, payload)
            return HttpResponse("Webhook processed successfully", status=status.HTTP_200_OK)
        except ValidationError as e:
            logger.warning(f"Rejet Webhook Wave: {e}")
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erreur interne Webhook Wave: {e}")
            return HttpResponse("Internal server error", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SasPayWebhookView(APIView):
    """Endpoint Webhook SasPay (POST https://api.votresite.com/api/v1/payments/saspay/webhook/)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get("X-Webhook-Signature", "")
        timestamp = request.headers.get("X-Webhook-Timestamp", "")
        event_type = request.headers.get("X-Webhook-Event", "")

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
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return HttpResponse("Internal server error", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
