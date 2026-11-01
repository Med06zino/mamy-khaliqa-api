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

from apps.orders.models import Order, Payment
from apps.orders.services import change_status

from .models import PaymentWebhookLog, SasPayCheckoutSession, WaveCheckoutSession
from .notifications import send_admin_order_notification

logger = logging.getLogger(__name__)

WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes de tolérance anti-rejeu


# ═══════════════════════════════════════════════════════════════════════════
# 1. INTÉGRATION WAVE BUSINESS (API Wave Sénégal)
# ═══════════════════════════════════════════════════════════════════════════

def create_wave_checkout_session(order):
    """Crée une session de paiement Wave Checkout.

    Appelle l'API officielle POST https://api.wave.com/v1/checkout/sessions
    Docs officielles : https://docs.wave.com

    Args:
        order: Instance de Order

    Returns:
        WaveCheckoutSession: Session enregistrée avec l'URL de redirection Wave
    """
    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"order": "Cette commande est déjà payée."})

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    api_key = getattr(settings, "WAVE_API_KEY", "")

    # Mode simulation si aucune clé n'est fournie ou en mode test local
    is_simulation = not api_key or api_key.startswith("wave_test_mock") or getattr(settings, "WAVE_SIMULATION_MODE", False)

    if is_simulation:
        logger.info(f"[WAVE SIMULATION] Création d'une session Wave simulée pour la commande {order.number}")
        sim_session_id = f"wave_sim_{secrets.token_hex(12)}"
        checkout_url = f"{frontend_url}/commande/paiement/succes/{order.number}?simulated=true&session_id={sim_session_id}"

        session, _ = WaveCheckoutSession.objects.update_or_create(
            order=order,
            defaults={
                "session_id": sim_session_id,
                "checkout_url": checkout_url,
                "amount": order.total,
                "currency": "XOF",
                "status": WaveCheckoutSession.Status.PENDING,
                "raw_response": {"simulated": True},
            },
        )
        return session

    # Appel réel à l'API Wave Checkout
    api_url = "https://api.wave.com/v1/checkout/sessions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "amount": str(order.total),
        "currency": "XOF",
        "error_url": f"{frontend_url}/commande/confirmation/{order.number}?payment_error=true",
        "success_url": f"{frontend_url}/commande/paiement/succes/{order.number}?provider=wave",
        "client_reference": order.number,
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=12)
        if response.status_code not in (200, 201):
            logger.error(f"Erreur API Wave ({response.status_code}): {response.text}")
            raise ValidationError({"wave": f"Erreur de communication avec Wave: {response.text}"})

        data = response.json()
        session_id = data.get("id")
        launch_url = data.get("wave_launch_url")

        if not launch_url:
            raise ValidationError({"wave": "L'API Wave n'a pas retourné d'URL de redirection."})

        session, _ = WaveCheckoutSession.objects.update_or_create(
            order=order,
            defaults={
                "session_id": session_id,
                "checkout_url": launch_url,
                "amount": order.total,
                "currency": data.get("currency", "XOF"),
                "status": WaveCheckoutSession.Status.PENDING,
                "raw_response": data,
            },
        )
        logger.info(f"Session Wave créée avec succès: {session.session_id} pour {order.number}")
        return session

    except requests.RequestException as e:
        logger.error(f"Exception réseau lors de la création de la session Wave: {e}")
        raise ValidationError({"wave": "Impossible de joindre le serveur de paiement Wave."})


def verify_wave_signature(raw_body: bytes, signature_header: str) -> bool:
    """Vérifie la signature HMAC SHA-256 du Webhook Wave.

    Header Wave-Signature format : t=1614555555,v1=5257186dbcdf...
    """
    secret = getattr(settings, "WAVE_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("WAVE_WEBHOOK_SECRET non configuré dans settings.")
        return False

    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    timestamp = parts.get("t")
    received_signature = parts.get("v1")

    if not timestamp or not received_signature:
        return False

    # Protection anti-rejeu (tolérance de 5 minutes)
    try:
        ts_int = int(timestamp)
        if abs(time.time() - ts_int) > WEBHOOK_TOLERANCE_SECONDS:
            logger.warning(f"Webhook Wave rejeté : horodatage expiré ({timestamp})")
            return False
    except ValueError:
        return False

    # Calcul de la signature attendue
    signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
    expected_signature = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, received_signature)


@transaction.atomic
def process_wave_webhook(raw_body: bytes, signature_header: str, payload: dict):
    """Traite un événement Webhook Wave vérifié et valide la commande."""
    event_id = payload.get("id", "")
    event_type = payload.get("type", "")

    # Journalisation de l'événement reçu
    log = PaymentWebhookLog.objects.create(
        provider="wave",
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        signature=signature_header,
        timestamp=str(int(time.time())),
        processed=False,
    )

    if not verify_wave_signature(raw_body, signature_header):
        log.error_message = "Signature Wave invalide."
        log.save()
        raise ValidationError("Signature de webhook invalide.")

    # Idempotence : si l'événement a déjà été traité avec succès
    if event_id and PaymentWebhookLog.objects.filter(provider="wave", event_id=event_id, processed=True).exists():
        logger.info(f"Événement Wave déjà traité (idempotence): {event_id}")
        return True

    # Traitement de l'événement de complétion de paiement
    if event_type == "checkout.session.completed":
        data = payload.get("data", {})
        client_ref = data.get("client_reference")  # Notre order.number
        session_id = data.get("id")
        amount = int(Decimal(str(data.get("amount", 0))))
        wave_txn_id = data.get("transaction_id", session_id)

        try:
            order = Order.objects.select_for_update().get(number=client_ref)
        except Order.DoesNotExist:
            log.error_message = f"Commande introuvable pour client_reference: {client_ref}"
            log.save()
            logger.error(log.error_message)
            return False

        # Vérification du montant
        if amount != order.total:
            logger.warning(f"Écart de montant Wave: reçu={amount}, attendu={order.total}")

        # Mise à jour de la session Wave
        session = WaveCheckoutSession.objects.filter(order=order).first()
        if session:
            session.status = WaveCheckoutSession.Status.PAID
            session.wave_transaction_id = wave_txn_id
            session.raw_response = data
            session.save()

        # Validation de la commande si non déjà payée
        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_method = "wave"
            order.save(update_fields=["payment_status", "payment_method", "updated_at"])

            if order.status == Order.Status.PENDING:
                change_status(order, Order.Status.CONFIRMED, note="Paiement Wave validé automatiquement par Webhook.")

            # Création ou mise à jour de l'enregistrement Payment
            Payment.objects.update_or_create(
                order=order,
                provider="wave",
                defaults={
                    "amount": order.total,
                    "status": Payment.Status.SUCCEEDED,
                    "provider_reference": wave_txn_id or session_id or "",
                    "raw_event_id": event_id,
                },
            )

            # Déclenchement automatique de la notification administrateur !
            send_admin_order_notification(order, provider="Wave")
            logger.info(f"Commande {order.number} marquée PAYÉE via Wave avec succès !")

    log.processed = True
    log.save()
    return True


@transaction.atomic
def simulate_wave_payment(session_id: str, success: bool = True):
    """Permet de simuler la validation d'un paiement Wave (développement local)."""
    try:
        session = WaveCheckoutSession.objects.select_for_update().get(session_id=session_id)
    except WaveCheckoutSession.DoesNotExist:
        raise ValidationError({"wave": "Session Wave introuvable"})

    order = session.order
    if success:
        session.status = WaveCheckoutSession.Status.PAID
        session.wave_transaction_id = f"txn_sim_{secrets.token_hex(8)}"
        session.save()

        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_method = "wave"
            order.save(update_fields=["payment_status", "payment_method", "updated_at"])

            if order.status == Order.Status.PENDING:
                change_status(order, Order.Status.CONFIRMED, note="Paiement Wave validé (simulation de test).")

            Payment.objects.update_or_create(
                order=order,
                provider="wave",
                defaults={
                    "amount": order.total,
                    "status": Payment.Status.SUCCEEDED,
                    "provider_reference": session.wave_transaction_id,
                },
            )
            # Notification automatique admin en simulation
            send_admin_order_notification(order, provider="Wave (Simulation)")
            logger.info(f"Simulation paiement Wave réussie pour {order.number}")
    else:
        session.status = WaveCheckoutSession.Status.FAILED
        session.save()

    return session


# ═══════════════════════════════════════════════════════════════════════════
# 2. INTÉGRATION PASSERELLE SASPAY
# ═══════════════════════════════════════════════════════════════════════════

def create_saspay_checkout_session(order):
    """Crée une session de paiement SasPay pour une commande."""
    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"order": "Cette commande est déjà payée."})

    api_key = getattr(settings, "SASPAY_API_KEY", "")
    base_url = getattr(settings, "SASPAY_BASE_URL", "https://api.saspay.me/api/v1").rstrip("/")
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")

    # Mode simulation si clé fictive
    if not api_key or api_key.startswith("sk_test_placeholder"):
        sim_session_id = f"saspay_sim_{secrets.token_hex(12)}"
        checkout_url = f"{frontend_url}/paiement/succes?order={order.number}&simulated=true&saspay={sim_session_id}"
        session, _ = SasPayCheckoutSession.objects.update_or_create(
            order=order,
            defaults={
                "session_id": sim_session_id,
                "checkout_url": checkout_url,
                "amount": order.total,
                "currency": "XOF",
                "status": SasPayCheckoutSession.Status.PENDING,
                "raw_response": {"simulated": True},
            },
        )
        return session

    api_url = f"{base_url}/checkout-sessions/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "amount": str(Decimal(order.total) / 100 if order.total > 100000 else order.total),
        "currency": "XOF",
        "description": f"Commande Mamy Khaliqa {order.number}",
        "customer_email": order.email or f"client_{order.id}@mamy-khaliqa.com",
        "customer_name": f"{order.first_name} {order.last_name}",
        "customer_phone": order.phone,
        "metadata": {"order_number": order.number},
        "success_url": f"{frontend_url}/commande/paiement/succes/{order.number}?provider=wave",
        "cancel_url": f"{frontend_url}/paiement/erreur?order={order.number}",
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=12)
        if response.status_code not in (200, 201):
            logger.error(f"Erreur SasPay ({response.status_code}): {response.text}")
            raise ValidationError({"saspay": f"Erreur de communication avec SasPay: {response.text}"})

        data = response.json()
        session_id = data.get("id")
        checkout_url = data.get("checkout_url")

        if not checkout_url:
            raise ValidationError({"saspay": "SasPay n'a pas renvoyé d'URL de paiement."})

        session, _ = SasPayCheckoutSession.objects.update_or_create(
            order=order,
            defaults={
                "session_id": session_id,
                "checkout_url": checkout_url,
                "amount": order.total,
                "currency": "XOF",
                "status": SasPayCheckoutSession.Status.PENDING,
                "raw_response": data,
            },
        )
        return session

    except requests.RequestException as e:
        logger.error(f"Exception réseau SasPay: {e}")
        raise ValidationError({"saspay": "Impossible de joindre la passerelle SasPay."})


def verify_saspay_signature(raw_body: bytes, signature: str, timestamp: str) -> bool:
    """Vérifie la signature HMAC SHA-256 du webhook SasPay."""
    secret = getattr(settings, "SASPAY_WEBHOOK_SECRET", "")
    if not secret:
        return True  # Si non configuré en dev

    try:
        ts_int = int(timestamp)
        if abs(time.time() - ts_int) > WEBHOOK_TOLERANCE_SECONDS:
            return False
    except ValueError:
        return False

    payload_to_sign = f"{timestamp}.".encode("utf-8") + raw_body
    computed = hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@transaction.atomic
def process_saspay_webhook(raw_body: bytes, signature: str, timestamp: str, event_type: str, payload: dict):
    """Traite un webhook reçu de SasPay."""
    event_id = payload.get("id", "")

    log = PaymentWebhookLog.objects.create(
        provider="saspay",
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        signature=signature,
        timestamp=timestamp,
        processed=False,
    )

    if not verify_saspay_signature(raw_body, signature, timestamp):
        log.error_message = "Signature SasPay invalide."
        log.save()
        raise ValidationError("Signature de webhook invalide.")

    if event_type in ("transaction.success", "payment.succeeded"):
        metadata = payload.get("metadata", {})
        order_number = metadata.get("order_number") or payload.get("client_reference")
        transaction_id = payload.get("id")

        if not order_number:
            logger.warning("Aucun order_number dans le payload SasPay.")
            return False

        try:
            order = Order.objects.select_for_update().get(number=order_number)
        except Order.DoesNotExist:
            logger.warning(f"Commande {order_number} non trouvée pour SasPay {transaction_id}")
            return False

        session = getattr(order, "saspay_session", None)
        if session:
            session.status = SasPayCheckoutSession.Status.PAID
            session.saspay_transaction_id = transaction_id
            session.save()

        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_method = "saspay"
            order.save(update_fields=["payment_status", "payment_method", "updated_at"])

            if order.status == Order.Status.PENDING:
                change_status(order, Order.Status.CONFIRMED, note="Paiement SasPay confirmé automatiquement par Webhook.")

            Payment.objects.update_or_create(
                order=order,
                provider="saspay",
                defaults={
                    "amount": order.total,
                    "status": Payment.Status.SUCCEEDED,
                    "provider_reference": transaction_id or "",
                    "raw_event_id": event_id,
                },
            )
            # Notification automatique admin
            send_admin_order_notification(order, provider="SasPay")

    log.processed = True
    log.save()
    return True
