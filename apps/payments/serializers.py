from rest_framework import serializers

from .models import SasPayCheckoutSession, WaveCheckoutSession


class WaveCheckoutSessionSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions de paiement Wave."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = WaveCheckoutSession
        fields = [
            "id",
            "session_id",
            "checkout_url",
            "amount",
            "currency",
            "status",
            "status_label",
            "order_number",
            "wave_transaction_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SasPayCheckoutSessionSerializer(serializers.ModelSerializer):
    """Serializer pour les sessions de paiement SasPay."""

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
