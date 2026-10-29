from rest_framework import serializers

from .models import DeliveryZone


class DeliveryZoneSerializer(serializers.ModelSerializer):
    """Serializer public — expose le délai estimé pour l'affichage côté client."""

    delivery_label = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryZone
        fields = ["id", "name", "fee", "info", "delivery_days_min", "delivery_days_max", "delivery_label"]

    def get_delivery_label(self, obj) -> str:
        """Retourne une chaîne lisible du délai, ex : '1–2 jours ouvrés'."""
        if obj.delivery_days_min == obj.delivery_days_max:
            return f"{obj.delivery_days_min} jour{'s' if obj.delivery_days_min > 1 else ''} ouvré{'s' if obj.delivery_days_min > 1 else ''}"
        return f"{obj.delivery_days_min}–{obj.delivery_days_max} jours ouvrés"


class AdminDeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = ["id", "name", "fee", "is_active", "info", "position",
                  "delivery_days_min", "delivery_days_max"]
