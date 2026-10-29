from rest_framework import serializers

from .models import SasPayCheckoutSession, SasPayWebhookLog


class SasPayCheckoutSessionSerializer(serializers.ModelSerializer):
    """Serializer pour créer une session de paiement SasPay."""

    class Meta:
        model = SasPayCheckoutSession
        fields = ["id", "checkout_url", "amount", "currency", "status"]
        read_only_fields = fields


class SasPayCheckoutSessionDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une session de paiement."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = SasPayCheckoutSession
        fields = [
            "id",
            "session_id",
            "checkout_url",
            "amount",
            "currency",
            "status",
            "status_label",
            "order_number",
            "saspay_transaction_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
