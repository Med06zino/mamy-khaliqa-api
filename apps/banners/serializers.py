from rest_framework import serializers

from .models import Banner


class BannerSerializer(serializers.ModelSerializer):
    """Serializer public : expose l'URL absolue de l'image."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ["id", "banner_type", "title", "subtitle", "image", "button_text", "link_url", "position"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class AdminBannerSerializer(serializers.ModelSerializer):
    """Serializer admin : tous les champs y compris les champs de gestion."""

    image = serializers.SerializerMethodField()
    image_upload = serializers.ImageField(write_only=True, required=False, source="image")

    class Meta:
        model = Banner
        fields = [
            "id", "banner_type", "title", "subtitle", "image", "image_upload",
            "button_text", "link_url", "position", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def create(self, validated_data):
        return Banner.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
