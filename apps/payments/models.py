import uuid
from django.db import models


class WaveCheckoutSession(models.Model):
    """Stocke les sessions de paiement Wave Business."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"
        EXPIRED = "expired", "Expiré"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="wave_session",
    )
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    checkout_url = models.URLField(max_length=500)
    amount = models.PositiveIntegerField(help_text="Montant en FCFA (XOF)")
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    wave_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Session Wave"
        verbose_name_plural = "Sessions Wave"

    def __str__(self):
        return f"Wave Session {self.session_id} - {self.get_status_display()} ({self.order.number})"


class SasPayCheckoutSession(models.Model):
    """Stocke les sessions de paiement SasPay."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"
        EXPIRED = "expired", "Expiré"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="saspay_session",
    )
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    checkout_url = models.URLField(max_length=500)
    amount = models.PositiveIntegerField(help_text="Montant en FCFA (XOF)")
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    saspay_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Session SasPay"
        verbose_name_plural = "Sessions SasPay"

    def __str__(self):
        return f"SasPay Session {self.session_id} - {self.get_status_display()} ({self.order.number})"


class PaymentWebhookLog(models.Model):
    """Journalisation et idempotence des événements Webhook reçus (Wave & SasPay)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=30, db_index=True)  # 'wave' ou 'saspay'
    event_id = models.CharField(max_length=255, blank=True, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    signature = models.CharField(max_length=500, blank=True)
    timestamp = models.CharField(max_length=50, blank=True)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log Webhook Paiement"
        verbose_name_plural = "Logs Webhooks Paiements"

    def __str__(self):
        return f"[{self.provider.upper()}] {self.event_type} ({self.created_at:%d/%m/%Y %H:%M})"
