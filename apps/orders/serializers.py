from rest_framework import serializers

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=50)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True, allow_empty=False)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30)
    address_line = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    delivery_zone = serializers.IntegerField(required=False, allow_null=True)
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    source = serializers.ChoiceField(choices=Order.Source.choices, required=False)


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.IntegerField(read_only=True)
    product_slug = serializers.SlugRelatedField(source="product", slug_field="slug", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id", "product", "product_slug", "product_name", "product_sku",
            "variant_name", "unit_price", "quantity", "line_total",
        ]


class HistorySerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ["status", "status_label", "note", "created_at"]


STATUS_ORDER = ["pending", "confirmed", "preparing", "shipped", "delivered", "cancelled"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_label = serializers.CharField(source="get_payment_status_display", read_only=True)
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "number", "source", "status", "status_label", "payment_status", "payment_status_label",
            "first_name", "last_name", "email", "phone", "address_line", "city", "delivery_zone_name",
            "customer_note", "subtotal", "delivery_fee", "delivery_fee_pending", "total", "tracking_info",
            "created_at", "items", "history", "allowed_transitions",
        ]

    def get_allowed_transitions(self, obj):
        from .services import TRANSITIONS

        allowed = TRANSITIONS.get(obj.status, set())
        return [s for s in STATUS_ORDER if s in allowed]


class OrderListSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_label = serializers.CharField(source="get_payment_status_display", read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["number", "status", "status_label", "payment_status", "payment_status_label", "total",
                  "created_at", "items_count", "first_name", "last_name", "phone"]

    def get_items_count(self, obj):
        return sum(i.quantity for i in obj.items.all())


class AdminOrderUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
    # L'interface admin ne propose que "Marquer comme payée". Les autres transitions (remboursement…)
    # passeront par une future interface dédiée. On accepte "paid" uniquement pour éviter les erreurs.
    payment_status = serializers.ChoiceField(
        choices=[(Order.PaymentStatus.PAID, Order.PaymentStatus.PAID.label)],
        required=False,
    )
    tracking_info = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delivery_fee = serializers.IntegerField(min_value=0, required=False)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
