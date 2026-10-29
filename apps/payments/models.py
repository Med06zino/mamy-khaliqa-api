import uuid

from django.conf import settings
from django.db import models


class WaveCheckoutSession(models.Model):
    """Stocke les sessions de paiement Wave simulées pour les tests."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="wave_session",
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
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
        return f"Wave Session {self.session_id} - {self.get_status_display()}"


class SasPayCheckoutSession(models.Model):
    """Stocke les sessions de checkout SasPay pour les commandes.

    Une session SasPay est créée quand un client choisit de payer via SasPay.
    Elle contient l'URL de redirection (checkout_url) et le statut du paiement.
    """
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
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    checkout_url = models.URLField(max_length=500)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
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
        return f"SasPay Session {self.session_id} - {self.get_status_display()}"


class SasPayWebhookLog(models.Model):
    """Journal des webhooks reçus de SasPay pour traçabilité et debug."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, db_index=True)
    payload = models.JSONField()
    signature = models.CharField(max_length=255)
    timestamp = models.CharField(max_length=20)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log webhook SasPay"
        verbose_name_plural = "Logs webhooks SasPay"

    def __str__(self):
        return f"Webhook {self.event_type} - {self.created_at}"
