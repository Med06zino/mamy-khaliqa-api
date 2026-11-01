import html
import logging
import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def build_order_notification_message(order, provider="Wave"):
    """Construit un message clair et détaillé pour l'administrateur."""
    items = order.items.all()
    items_text = "\n".join(
        f"  • {it.quantity}x {it.product_name}"
        + (f" ({it.variant_name})" if it.variant_name else "")
        + f" — {it.line_total:,} FCFA"
        for it in items
    )

    client_name = f"{order.first_name} {order.last_name}".strip()
    zone_info = order.delivery_zone_name or order.city or "Non spécifiée"
    admin_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/admin/commandes/{order.number}"

    msg = (
        f"🔔 *NOUVELLE COMMANDE PAYÉE SUR MAMY KHALIQA*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *N° Commande* : `{order.number}`\n"
        f"💳 *Paiement* : {provider.upper()} (Validé ✅)\n"
        f"💰 *Total encaissé* : *{order.total:,} FCFA*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Client* : {client_name}\n"
        f"📞 *Téléphone* : {order.phone}\n"
        f"📧 *Email* : {order.email or 'Non renseigné'}\n"
        f"📍 *Adresse de livraison* : {order.address_line} ({zone_info})\n"
    )

    if order.customer_note:
        msg += f"📝 *Note client* : _{order.customer_note}_\n"

    msg += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ *Articles commandés* :\n{items_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Gérer la commande* : {admin_url}"
    )
    return msg


def send_telegram_notification(message):
    """Envoie une notification push instantanée à l'administrateur via un bot Telegram (100% gratuit)."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", None)

    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code == 200:
            logger.info("Notification Telegram admin envoyée avec succès.")
            return True
        else:
            logger.warning(f"Échec envoi Telegram: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"Erreur d'envoi Telegram: {e}")
    return False


def send_whatsapp_ultramsg_notification(message):
    """Envoie un message WhatsApp à l'administrateur via UltraMsg."""
    instance_id = getattr(settings, "ULTRAMSG_INSTANCE_ID", None)
    token = getattr(settings, "ULTRAMSG_TOKEN", None)
    to_number = getattr(settings, "ADMIN_WHATSAPP_NUMBER", getattr(settings, "DEFAULT_WHATSAPP_NUMBER", None))

    if not instance_id or not token or not to_number:
        return False

    # Format international sans '+'
    to_clean = to_number.replace("+", "").replace(" ", "").strip()
    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    payload = {
        "token": token,
        "to": to_clean,
        "body": message.replace("`", "*"),  # WhatsApp prend en charge le gras *texte*
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if str(data.get("sent", "")).lower() in ("true", "1") or "id" in data:
                logger.info(f"Notification WhatsApp UltraMsg envoyée avec succès à {to_clean}.")
                return True
            else:
                logger.warning(f"Réponse UltraMsg inattendue: {resp.text}")
        else:
            logger.warning(f"Échec envoi WhatsApp UltraMsg ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"Erreur d'envoi WhatsApp UltraMsg: {e}")
    return False


def send_discord_notification(message):
    """Envoie une notification dans un canal Discord admin via Webhook (gratuit)."""
    webhook_url = getattr(settings, "DISCORD_WEBHOOK_URL", None)
    if not webhook_url:
        return False

    payload = {
        "content": message.replace("`", "```"),
        "username": "Mamy Khaliqa Bot",
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=8)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Erreur d'envoi Discord: {e}")
    return False


def send_email_notification(order, message, provider="Wave"):
    """Envoi de secours par email à l'administrateur."""
    admin_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", getattr(settings, "DEFAULT_FROM_EMAIL", None))
    if not admin_email:
        return False

    subject = f"💰 Paiement {provider.upper()} reçu - Commande {order.number} ({order.total:,} FCFA)"
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "Mamy Khaliqa <no-reply@example.com>"),
            recipient_list=[admin_email],
            fail_silently=True,
        )
        logger.info(f"Notification email envoyée à {admin_email}")
        return True
    except Exception as e:
        logger.error(f"Erreur d'envoi d'email de notification: {e}")
        return False


def send_admin_order_notification(order, provider="Wave"):
    """Déclencheur centralisé des notifications administratives multi-canaux."""
    message = build_order_notification_message(order, provider=provider)
    logger.info(f"Déclenchement des notifications pour la commande {order.number} ({provider})...")

    # Envoi en parallèle ou séquentiel
    telegram_sent = send_telegram_notification(message)
    whatsapp_sent = send_whatsapp_ultramsg_notification(message)
    discord_sent = send_discord_notification(message)
    email_sent = send_email_notification(order, message, provider=provider)

    logger.info(
        f"Bilan notifications commande {order.number}: "
        f"Telegram={telegram_sent}, WhatsApp={whatsapp_sent}, Discord={discord_sent}, Email={email_sent}"
    )
