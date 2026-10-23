from rest_framework import serializers

from apps.catalog.models import Product
from apps.orders.models import Order

from .models import Review


def user_can_review(user, product):
    """Un avis n'est possible qu'apres reception du produit, et une seule fois."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    bought = Order.objects.filter(
        user=user, status=Order.Status.DELIVERED, items__product=product
    ).exists()
    if not bought:
        return False
    return not Review.objects.filter(user=user, product=product).exists()


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    product_slug = serializers.SlugRelatedField(source="product", slug_field="slug", read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.public(), write_only=True)

    class Meta:
        model = Review
        fields = ["id", "product", "product_slug", "rating", "comment", "author", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_author(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name[:1]}.".strip()

    def validate(self, data):
        user = self.context["request"].user
        product = data["product"]
        bought = Order.objects.filter(
            user=user, status=Order.Status.DELIVERED, items__product=product
        ).exists()
        if not bought:
            raise serializers.ValidationError("Seuls les clients ayant recu ce produit peuvent laisser un avis.")
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("Vous avez deja donne votre avis sur ce produit.")
        return data


class AdminReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "product_name", "user_email", "rating", "comment", "is_approved", "created_at"]
        read_only_fields = ["rating", "comment", "created_at"]
