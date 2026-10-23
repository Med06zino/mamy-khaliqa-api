from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "phone", "subject", "message", "is_read", "created_at"]
        # is_read est en lecture seule pour la création publique.
        # L'admin peut le modifier via PATCH grâce à AdminContactSerializer ci-dessous.
        read_only_fields = ["id", "created_at"]


class AdminContactSerializer(serializers.ModelSerializer):
    """Serializer admin : autorise la mise à jour de is_read via PATCH."""

    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "phone", "subject", "message", "is_read", "created_at"]
        read_only_fields = ["id", "name", "email", "phone", "subject", "message", "created_at"]
