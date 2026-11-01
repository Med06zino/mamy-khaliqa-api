import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.orders.models import Order
from apps.payments.notifications import send_whatsapp_ultramsg_notification


class Command(BaseCommand):
    help = "Vérifie l'état de l'instance UltraMsg et envoie une notification de test."

    def add_arguments(self, parser):
        parser.add_argument("--phone", type=str, help="Numéro WhatsApp de destination (format international sans +, ex: 221771234567)")

    def handle(self, *args, **options):
        instance_id = getattr(settings, "ULTRAMSG_INSTANCE_ID", "")
        token = getattr(settings, "ULTRAMSG_TOKEN", "")
        phone = options.get("phone") or getattr(settings, "ADMIN_WHATSAPP_NUMBER", "")

        self.stdout.write(self.style.MIGRATE_HEADING("=== Test UltraMsg WhatsApp Mamy Khaliqa ==="))
        self.stdout.write(f"Instance ID : {instance_id}")
        self.stdout.write(f"Destinataire : {phone}")

        if not instance_id or not token:
            self.stdout.write(self.style.ERROR("[ERREUR] Instance ID ou Token UltraMsg manquant dans .env"))
            return

        # 1. Vérification du statut de l'instance
        status_url = f"https://api.ultramsg.com/{instance_id}/instance/status?token={token}"
        try:
            res = requests.get(status_url, timeout=10)
            data = res.json()
            account_status = data.get("status", {}).get("accountStatus", {}).get("status", "unknown")
            self.stdout.write(f"Statut WhatsApp : {account_status}")

            if account_status == "qr":
                qr_url = f"https://api.ultramsg.com/{instance_id}/instance/qr?token={token}"
                self.stdout.write(self.style.WARNING(
                    f"\n[ATTENTION] Votre instance WhatsApp n'est pas encore connectée.\n"
                    f"Veuillez scanner le QR Code ici : {qr_url}\n"
                    f"Sur votre téléphone : WhatsApp > Appareils connectés > Connecter un appareil.\n"
                ))
                return
            elif account_status == "authenticated":
                self.stdout.write(self.style.SUCCESS("[OK] Instance WhatsApp connectée et prête à envoyer des messages !"))
            else:
                self.stdout.write(f"Info instance : {data}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur de communication UltraMsg : {e}"))
            return

        # 2. Envoi d'un message de test
        latest_order = Order.objects.order_by("-created_at").first()
        order_num = latest_order.number if latest_order else "MK-TEST-001"
        order_total = latest_order.total if latest_order else 15000

        test_message = (
            f"🚨 *TEST NOTIFICATION MAMY KHALIQA* 🚨\n\n"
            f"✅ Félicitations ! Votre passerelle WhatsApp UltraMsg fonctionne parfaitement.\n\n"
            f"📦 *Exemple de commande :* {order_num}\n"
            f"💰 *Montant :* {order_total:,} FCFA\n"
            f"💳 *Paiement :* Validé automatiquement par Wave Sénégal\n\n"
            f"Les futures commandes payées vous seront notifiées ici en temps réel."
        )

        self.stdout.write("Envoi du message WhatsApp de test...")
        # Si un numéro a été spécifié en argument
        if options.get("phone"):
            url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
            resp = requests.post(url, data={
                "token": token,
                "to": phone.replace("+", "").strip(),
                "body": test_message,
            }, timeout=10)
            if resp.status_code == 200:
                self.stdout.write(self.style.SUCCESS(f"[SUCCÈS] Message de test envoyé avec succès à {phone} !"))
            else:
                self.stdout.write(self.style.ERROR(f"[ÉCHEC] Réponse API : {resp.text}"))
        else:
            success = send_whatsapp_ultramsg_notification(test_message)
            if success:
                self.stdout.write(self.style.SUCCESS("[SUCCÈS] Notification envoyée !"))
            else:
                self.stdout.write(self.style.ERROR("[ÉCHEC] Échec de l'envoi. Vérifiez le numéro de téléphone."))
