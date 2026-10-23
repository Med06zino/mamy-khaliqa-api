from rest_framework import serializers

from .models import StoreSettings

PUBLIC_FIELDS = [
    "name", "tagline", "logo", "contact_email", "contact_phone", "address", "whatsapp_number",
    "instagram_url", "facebook_url", "tiktok_url", "announcement_text", "announcement_active",
    "footer_text", "guest_checkout_enabled", "payment_cash_on_delivery", "unknown_zone_policy",
]


class PublicStoreSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        fields = PUBLIC_FIELDS
        read_only_fields = PUBLIC_FIELDS


class AdminStoreSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        fields = PUBLIC_FIELDS + ["low_stock_threshold"]

    def validate_whatsapp_number(self, v):
        v = v.strip().replace(" ", "").lstrip("+")
        if v and not v.isdigit():
            raise serializers.ValidationError("Utilisez uniquement des chiffres, au format international.")
        return v
