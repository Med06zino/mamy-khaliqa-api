from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Invoice, Order
from .pdf import generate_invoice_pdf, send_invoice_email


@receiver(post_save, sender=Order)
def create_invoice_and_send_email(sender, instance, created, **kwargs):
    """Crée automatiquement une facture après création de commande et l'envoie par email."""
    if created:
        # La facture est déjà créée automatiquement par le signal dans models.py
        # On génère et envoie le PDF par email
        try:
            invoice = instance.invoice
            pdf_buffer = generate_invoice_pdf(instance)
            send_invoice_email(instance, pdf_buffer)
        except Exception as e:
            # Log l'erreur mais ne pas bloquer la création de commande
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la génération/envoi de la facture pour la commande {instance.number}: {str(e)}")
