import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Invoice, Order
from .pdf import generate_invoice_pdf, send_invoice_email

logger = logging.getLogger(__name__)


def ensure_invoice_exists(order: Order) -> Invoice:
    """Crée ou récupère la facture liée à une commande avec son snapshot immuable."""
    try:
        return order.invoice
    except Order.invoice.RelatedObjectDoesNotExist:
        snapshot = {
            "order_number": order.number,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "first_name": order.first_name,
            "last_name": order.last_name,
            "email": order.email,
            "phone": order.phone,
            "address_line": order.address_line,
            "city": order.city,
            "delivery_zone": order.delivery_zone_name,
            "subtotal": order.subtotal,
            "delivery_fee": order.delivery_fee,
            "total": order.total,
            "payment_method": order.payment_method,
            "items": [
                {
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "unit_price": item.unit_price,
                    "quantity": item.quantity,
                    "line_total": item.line_total,
                }
                for item in order.items.all()
            ],
        }
        invoice, _ = Invoice.objects.get_or_create(
            order=order,
            defaults={
                "number": Invoice.generate_number(order.number),
                "snapshot": snapshot,
            },
        )
        return invoice


@receiver(post_save, sender=Order)
def create_invoice_and_send_email(sender, instance, created, **kwargs):
    """Crée automatiquement une facture après création de commande et l'envoie par email."""
    if created:
        try:
            ensure_invoice_exists(instance)
            pdf_buffer = generate_invoice_pdf(instance)
            send_invoice_email(instance, pdf_buffer)
        except Exception as e:
            logger.error(
                f"Erreur lors de la génération/envoi de la facture pour la commande {instance.number}: {str(e)}"
            )
