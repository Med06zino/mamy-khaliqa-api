from rest_framework import serializers

from .models import NewsletterSubscriber


class SubscribeSerializer(serializers.Serializer):
    """Abonnement public : seulement l'e-mail."""

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class AdminNewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ["id", "email", "is_active", "subscribed_at"]
        read_only_fields = ["id", "email", "subscribed_at"]
