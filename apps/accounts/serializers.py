from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from rest_framework import serializers

from .models import Address, Favorite, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "is_staff"]
        read_only_fields = ["id", "email", "is_staff"]


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    accept_terms = serializers.BooleanField()

    def validate_email(self, v):
        v = v.lower()
        if User.objects.filter(email=v).exists():
            raise serializers.ValidationError("Un compte existe deja avec cet e-mail.")
        return v

    def validate_accept_terms(self, v):
        if not v:
            raise serializers.ValidationError("Vous devez accepter les conditions generales de vente.")
        return v

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas."})
        password_validation.validate_password(data["password"])
        return data

    def create(self, validated):
        validated.pop("password_confirm")
        validated.pop("accept_terms")
        pwd = validated.pop("password")
        return User.objects.create_user(password=pwd, accepted_terms_at=timezone.now(), **validated)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(self.context["request"], username=data["email"].lower(), password=data["password"])
        if not user or not user.is_active:
            raise serializers.ValidationError("E-mail ou mot de passe incorrect.")
        data["user"] = user
        return data


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_password(self, v):
        password_validation.validate_password(v)
        return v


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, v):
        password_validation.validate_password(v, self.context["request"].user)
        return v


class AddressSerializer(serializers.ModelSerializer):
    delivery_zone_name = serializers.CharField(source="delivery_zone.name", read_only=True)

    class Meta:
        model = Address
        fields = ["id", "label", "recipient_name", "phone", "line1", "city", "delivery_zone",
                  "delivery_zone_name", "is_default"]


class FavoriteSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "product", "product_id", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_product(self, obj):
        from apps.catalog.serializers import ProductListSerializer

        return ProductListSerializer(obj.product, context=self.context).data

    def validate_product_id(self, v):
        from apps.catalog.models import Product

        if not Product.objects.public().filter(pk=v).exists():
            raise serializers.ValidationError("Produit introuvable.")
        return v


class AdminCustomerSerializer(serializers.ModelSerializer):
    orders_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "date_joined", "is_active", "orders_count"]
