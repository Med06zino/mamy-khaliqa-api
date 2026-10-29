import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_order_number():
    return f"MK-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmée"
        PREPARING = "preparing", "En préparation"
        SHIPPED = "shipped", "Expédiée"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Non payée"
        PAID = "paid", "Payée"
        REFUNDED = "refunded", "Remboursée"

    class Source(models.TextChoices):
        WEB = "web", "Site"
        WHATSAPP = "whatsapp", "WhatsApp"

    number = models.CharField(max_length=24, unique=True, default=generate_order_number, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEB)

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True)
    delivery_zone = models.ForeignKey(
        "deliveries.DeliveryZone", null=True, blank=True, on_delete=models.SET_NULL
    )
    delivery_zone_name = models.CharField(max_length=120, blank=True)
    customer_note = models.TextField(blank=True)

    subtotal = models.PositiveIntegerField()
    delivery_fee = models.PositiveIntegerField(default=0)
    delivery_fee_pending = models.BooleanField(
        default=False, help_text="Frais a confirmer (zone non configuree)."
    )
    total = models.PositiveIntegerField()

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True
    )
    payment_method = models.CharField(max_length=30, blank=True)
    tracking_info = models.CharField("Informations de suivi", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False, user__isnull=False),
                name="uniq_user_idempotency",
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False, user__isnull=True),
                name="uniq_guest_idempotency",
            ),
        ]

    def __str__(self):
        return self.number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, on_delete=models.SET_NULL)
    variant = models.ForeignKey("catalog.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=60)
    variant_name = models.CharField(max_length=120, blank=True)
    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Payment(models.Model):
    """Structure preparee pour la phase 2 (Wave, Orange Money...). Non utilisee en V1."""

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initie"
        SUCCEEDED = "succeeded", "Reussi"
        FAILED = "failed", "Echoue"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=30)
    provider_reference = models.CharField(max_length=120, blank=True)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INITIATED)
    raw_event_id = models.CharField(max_length=120, blank=True, db_index=True)  # idempotence des webhooks
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                condition=~models.Q(provider_reference=""),
                name="uniq_provider_reference",
            )
        ]


class Invoice(models.Model):
    """Facture liée à une commande.

    Créée automatiquement (signal post_save) dès qu'une commande est enregistrée.
    Stocke un snapshot des données au moment de la commande pour garantir
    l'immuabilité : même si les prix ou adresses changent plus tard, la facture
    conserve les valeurs d'origine.

    Règle métier :
    - Une commande a exactement une facture (OneToOne).
    - Le numéro de facture est distinct du numéro de commande.
    - La facture est accessible uniquement au client propriétaire et aux admins.
    - Une facture sur une commande non payée est clairement marquée "en attente de paiement".
    """

    number   = models.CharField("Numéro de facture", max_length=30, unique=True, editable=False)
    order    = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    # Snapshot des données à la création — immuables
    snapshot = models.JSONField(
        "Données de la facture",
        help_text="Snapshot JSON des données commande au moment de la création.",
    )
    issued_at = models.DateTimeField("Date d'émission", auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "Facture"
        verbose_name_plural = "Factures"

    def __str__(self):
        return self.number

    @staticmethod
    def generate_number(order_number: str) -> str:
        """Génère un numéro de facture à partir du numéro de commande.
        Ex : MK-261025-AB12CD → FAC-261025-AB12CD
        """
        return order_number.replace("MK-", "FAC-", 1)
