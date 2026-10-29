import hashlib
import hmac
import logging
import secrets
import time
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import SasPayCheckoutSession, SasPayWebhookLog, WaveCheckoutSession

logger = logging.getLogger(__name__)

# Tolérance de 5 minutes pour la vérification des webhooks
WEBHOOK_TOLERANCE_SECONDS = 300


def create_wave_checkout_session(order):
    """Crée une session de paiement Wave simulée pour les tests.

    Cette fonction simule l'API Wave en mode test.
    En production, elle sera remplacée par l'API Wave officielle.

    Args:
        order: Instance de Order

    Returns:
        WaveCheckoutSession: La session créée avec checkout_url simulé
    """
    # Simuler la création d'une session Wave
    session_id = f"wave_test_{secrets.token_hex(16)}"

    # En mode simulation, générer une URL locale pour tester
    checkout_url = f"{settings.FRONTEND_URL}/wave/payment/{session_id}"

    # Créer ou mettre à jour la session locale
    session, created = WaveCheckoutSession.objects.update_or_create(
        order=order,
        defaults={
            "session_id": session_id,
            "checkout_url": checkout_url,
            "amount": Decimal(order.total) / 100,
            "currency": "XOF",
            "status": WaveCheckoutSession.Status.PENDING,
            "raw_response": {"simulated": True, "test_mode": True},
        },
    )

    logger.info(f"Wave session created for order {order.number}: {session.session_id}")
    return session


def simulate_wave_payment(session_id, success=True):
    """Simule un paiement Wave réussi ou échoué.

    Cette fonction est utilisée uniquement pour les tests.
    En production, le paiement sera traité par les webhooks Wave.

    Args:
        session_id: ID de la session Wave
        success: True pour simuler un succès, False pour un échec

    Returns:
        WaveCheckoutSession: La session mise à jour
    """
    try:
        session = WaveCheckoutSession.objects.get(session_id=session_id)
    except WaveCheckoutSession.DoesNotExist:
        raise ValidationError({"wave": "Session Wave introuvable"})

    if session.status != WaveCheckoutSession.Status.PENDING:
        raise ValidationError({"wave": "Cette session n'est plus en attente"})

    # Simuler le paiement
    if success:
        session.status = WaveCheckoutSession.Status.PAID
        session.wave_transaction_id = f"txn_{secrets.token_hex(16)}"

        # Mettre à jour la commande
        from apps.orders.models import Order
        from apps.orders.services import change_status

        order = session.order
        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_method = "wave"
            order.save(update_fields=["payment_status", "payment_method"])

            if order.status == Order.Status.PENDING:
                change_status(order, Order.Status.CONFIRMED, note="Paiement Wave confirmé (simulation)")

        logger.info(f"Wave payment simulated successfully for order {order.number}")
    else:
        session.status = WaveCheckoutSession.Status.FAILED
        logger.warning(f"Wave payment simulated as failed for order {session.order.number}")

    session.save()
    return session


def create_saspay_checkout_session(order):
    """Crée une session de checkout SasPay pour une commande.

    Utilise l'endpoint officiel POST /checkout-sessions/
    Documentation: https://docs.saspay.me/api-reference/payments/checkout-create

    Args:
        order: Instance de Order

    Returns:
        SasPayCheckoutSession: La session créée avec checkout_url

    Raises:
        ValidationError: Si l'appel API échoue ou si SasPay n'est pas configuré
    """
    api_key = settings.SASPAY_API_KEY

    # Vérifier que SasPay est configuré
    if not api_key or api_key == "sk_test_placeholder":
        logger.warning(f"SasPay not configured (placeholder key). Order {order.number}")
        raise ValidationError(
            {"saspay": "Le paiement en ligne SasPay n'est pas configuré. Veuillez contacter l'administrateur ou choisir un autre mode de paiement."}
        )

    api_url = f"{settings.SASPAY_BASE_URL}/checkout-sessions/"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Construction du payload selon la documentation SasPay
    payload = {
        "amount": str(Decimal(order.total) / 100),  # Convertir les centimes en décimal
        "currency": "XOF",
        "description": f"Commande {order.number}",
        "customer_email": order.email or f"customer_{order.id}@example.com",
        "customer_name": f"{order.first_name} {order.last_name}",
        "customer_phone": order.phone,
        "country": "SN",  # Sénégal par défaut
        "return_url": f"{settings.FRONTEND_URL}/commande/paiement/succes/{order.number}",
        "metadata": {
            "order_number": order.number,
            "order_id": order.id,
        },
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            error = data.get("error", {})
            raise ValidationError(
                {"saspay": f"Erreur SasPay: {error.get('message', 'Erreur inconnue')}"}
            )

        session_data = data["data"]

        # Créer ou mettre à jour la session locale
        session, created = SasPayCheckoutSession.objects.update_or_create(
            order=order,
            defaults={
                "session_id": session_data["id"],
                "checkout_url": session_data["checkout_url"],
                "amount": Decimal(session_data["amount"]),
                "currency": session_data["currency"],
                "status": _map_saspay_status(session_data.get("status", "PENDING")),
                "raw_response": session_data,
            },
        )

        logger.info(f"SasPay session created for order {order.number}: {session.session_id}")
        return session

    except requests.RequestException as e:
        logger.error(f"SasPay API error for order {order.number}: {str(e)}")
        raise ValidationError({"saspay": f"Erreur de connexion à SasPay: {str(e)}"})


def verify_saspay_payment(session_id):
    """Vérifie le statut d'un paiement auprès de SasPay.

    Utilise l'endpoint GET /checkout-sessions/{id}/
    Documentation: https://docs.saspay.me/api-reference/payments/checkout-status

    Args:
        session_id: UUID de la session SasPay

    Returns:
        dict: Les données de statut de la session

    Raises:
        ValidationError: Si l'appel API échoue
    """
    api_url = f"{settings.SASPAY_BASE_URL}/checkout-sessions/{session_id}/"
    api_key = settings.SASPAY_API_KEY

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            error = data.get("error", {})
            raise ValidationError(
                {"saspay": f"Erreur SasPay: {error.get('message', 'Erreur inconnue')}"}
            )

        return data["data"]

    except requests.RequestException as e:
        logger.error(f"SasPay verification error for session {session_id}: {str(e)}")
        raise ValidationError({"saspay": f"Erreur de vérification SasPay: {str(e)}"})


def verify_webhook_signature(raw_body, signature, timestamp, secret):
    """Vérifie la signature HMAC-SHA256 d'un webhook SasPay.

    Documentation: https://docs.saspay.me/api-reference/webhooks#sécurité--vérifier-la-signature

    Args:
        raw_body: Corps brut de la requête (bytes)
        signature: Header X-Webhook-Signature
        timestamp: Header X-Webhook-Timestamp
        secret: Signing secret du webhook

    Returns:
        bool: True si signature valide, False sinon
    """
    # Vérifier l'âge du timestamp (tolérance 5 minutes)
    now = int(time.time())
    if abs(now - int(timestamp)) > WEBHOOK_TOLERANCE_SECONDS:
        logger.warning(f"Webhook timestamp too old: {timestamp}")
        return False

    # Calculer la signature attendue
    signed = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(
        secret.encode(), signed, hashlib.sha256
    ).hexdigest()

    # Comparaison en temps constant pour éviter les attaques par timing
    return hmac.compare_digest(expected, signature)


def process_saspay_webhook(raw_body, signature, timestamp, event_type, payload):
    """Traite un webhook reçu de SasPay.

    Args:
        raw_body: Corps brut de la requête (bytes)
        signature: Header X-Webhook-Signature
        timestamp: Header X-Webhook-Timestamp
        event_type: Header X-Webhook-Event
        payload: Corps JSON du webhook

    Returns:
        bool: True si traité avec succès

    Raises:
        ValidationError: Si signature invalide ou erreur de traitement
    """
    # Vérifier la signature
    if not verify_webhook_signature(
        raw_body, signature, timestamp, settings.SASPAY_WEBHOOK_SECRET
    ):
        # Logger le webhook mais ne pas le traiter
        SasPayWebhookLog.objects.create(
            event_type=event_type,
            payload=payload,
            signature=signature,
            timestamp=timestamp,
            processed=False,
            error_message="Signature invalide",
        )
        raise ValidationError({"webhook": "Signature invalide"})

    # Logger le webhook
    log = SasPayWebhookLog.objects.create(
        event_type=event_type,
        payload=payload,
        signature=signature,
        timestamp=timestamp,
        processed=False,
    )

    try:
        # Traiter selon le type d'événement
        if event_type == "transaction.success":
            _handle_transaction_success(payload, log)
        elif event_type == "transaction.failed":
            _handle_transaction_failed(payload, log)
        elif event_type == "transaction.cancelled":
            _handle_transaction_cancelled(payload, log)
        else:
            logger.info(f"Event type {event_type} not handled, logged only")

        log.processed = True
        log.save()
        return True

    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {str(e)}")
        log.error_message = str(e)
        log.save()
        raise


def _handle_transaction_success(payload, log):
    """Traite un événement transaction.success."""
    from apps.orders.models import Order
    from apps.orders.services import change_status

    # Récupérer l'ID de transaction depuis le payload
    transaction_id = payload.get("id")
    reference = payload.get("reference")
    amount = Decimal(payload.get("amount", "0"))
    currency = payload.get("currency")

    logger.info(f"Transaction success: {transaction_id}, ref: {reference}, amount: {amount}")

    # Trouver la session SasPay correspondante via metadata
    # Le metadata contient order_number passé lors de la création
    metadata = payload.get("metadata", {})
    order_number = metadata.get("order_number")

    if not order_number:
        logger.warning(f"No order_number in metadata for transaction {transaction_id}")
        return

    try:
        order = Order.objects.get(number=order_number)
    except Order.DoesNotExist:
        logger.warning(f"Order {order_number} not found for transaction {transaction_id}")
        return

    # Vérifier que le montant correspond
    expected_amount = Decimal(order.total) / 100
    if abs(amount - expected_amount) > Decimal("0.01"):
        logger.error(
            f"Amount mismatch for order {order_number}: expected {expected_amount}, got {amount}"
        )
        return

    # Mettre à jour la session SasPay
    session = getattr(order, "saspay_session", None)
    if session:
        session.status = SasPayCheckoutSession.Status.PAID
        session.saspay_transaction_id = transaction_id
        session.save()

    # Marquer la commande comme payée
    if order.payment_status != Order.PaymentStatus.PAID:
        order.payment_status = Order.PaymentStatus.PAID
        order.payment_method = "saspay"
        order.save(update_fields=["payment_status", "payment_method"])

        # Passer la commande en CONFIRMED si elle était PENDING
        if order.status == Order.Status.PENDING:
            change_status(order, Order.Status.CONFIRMED, note="Paiement SasPay confirmé")

        logger.info(f"Order {order_number} marked as paid via SasPay")


def _handle_transaction_failed(payload, log):
    """Traite un événement transaction.failed."""
    from apps.orders.models import Order

    transaction_id = payload.get("id")
    metadata = payload.get("metadata", {})
    order_number = metadata.get("order_number")

    if not order_number:
        return

    try:
        order = Order.objects.get(number=order_number)
    except Order.DoesNotExist:
        return

    # Mettre à jour la session SasPay
    session = getattr(order, "saspay_session", None)
    if session:
        session.status = SasPayCheckoutSession.Status.FAILED
        session.saspay_transaction_id = transaction_id
        session.save()

    logger.info(f"Order {order_number} payment failed via SasPay")


def _handle_transaction_cancelled(payload, log):
    """Traite un événement transaction.cancelled."""
    from apps.orders.models import Order

    transaction_id = payload.get("id")
    metadata = payload.get("metadata", {})
    order_number = metadata.get("order_number")

    if not order_number:
        return

    try:
        order = Order.objects.get(number=order_number)
    except Order.DoesNotExist:
        return

    # Mettre à jour la session SasPay
    session = getattr(order, "saspay_session", None)
    if session:
        session.status = SasPayCheckoutSession.Status.CANCELLED
        session.saspay_transaction_id = transaction_id
        session.save()

    logger.info(f"Order {order_number} payment cancelled via SasPay")


def _map_saspay_status(saspay_status):
    """Mappe les statuts SasPay vers nos statuts locaux."""
    mapping = {
        "PENDING": SasPayCheckoutSession.Status.PENDING,
        "PAID": SasPayCheckoutSession.Status.PAID,
        "FAILED": SasPayCheckoutSession.Status.FAILED,
        "CANCELLED": SasPayCheckoutSession.Status.CANCELLED,
        "EXPIRED": SasPayCheckoutSession.Status.EXPIRED,
    }
    return mapping.get(saspay_status, SasPayCheckoutSession.Status.PENDING)
