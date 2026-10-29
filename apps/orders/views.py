from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.common.permissions import IsStaffUser
from apps.store_settings.models import StoreSettings

from .models import Order, OrderItem
from .pdf import generate_invoice_pdf, send_invoice_email
from .serializers import (
    AdminOrderUpdateSerializer, InvoiceSerializer,
    OrderCreateSerializer, OrderListSerializer, OrderSerializer,
)
from .services import change_status, create_order


class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_field = "number"
    throttle_scope = "orders"

    def get_permissions(self):
        return [AllowAny()] if self.action == "create" else [IsAuthenticated()]

    def get_throttles(self):
        # Limitation uniquement sur la creation de commande.
        return super().get_throttles() if self.action == "create" else []

    def get_queryset(self):
        # Isolation : un client ne voit que ses propres commandes.
        return Order.objects.filter(user=self.request.user).prefetch_related("items", "history")

    def get_serializer_class(self):
        return OrderListSerializer if self.action == "list" else OrderSerializer

    def create(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        if user is None and not StoreSettings.load().guest_checkout_enabled:
            raise PermissionDenied("Connectez-vous pour passer commande.")
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        key = (request.headers.get("Idempotency-Key") or "")[:64] or None
        order, created = create_order(user=user, data=s.validated_data, idempotency_key=key)
        return Response(OrderSerializer(order).data, status=201 if created else 200)

    @action(detail=True, methods=["get"])
    def invoice(self, request, number=None):
        """GET /api/v1/orders/{number}/invoice/

        Retourne la facture de la commande.
        - Le client n'accède qu'à ses propres factures (isolation garantie par get_object()).
        - Si la facture n'existe pas encore (commande très récente), retourne 404.
        """
        order = self.get_object()
        try:
            inv = order.invoice
        except order.__class__.invoice.RelatedObjectDoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Facture non encore disponible. Réessayez dans quelques secondes.")
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["get"], url_path="invoice/download")
    def download_invoice(self, request, number=None):
        """GET /api/v1/orders/{number}/invoice/download/

        Télécharge la facture PDF de la commande.
        """
        order = self.get_object()
        try:
            inv = order.invoice
        except order.__class__.invoice.RelatedObjectDoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Facture non encore disponible.")

        pdf_buffer = generate_invoice_pdf(order)
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Facture_{inv.number}.pdf"'
        return response
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            raise ValidationError({"status": "Seule une commande en attente peut etre annulee. Contactez la boutique."})
        order = change_status(order, Order.Status.CANCELLED, by=request.user, note="Annulee par le client.")
        return Response(OrderSerializer(order).data)


class AdminOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsStaffUser]
    lookup_field = "number"
    search_fields = ["number", "first_name", "last_name", "phone", "email"]
    filterset_fields = ["status", "payment_status", "source"]
    ordering_fields = ["created_at", "total"]
    ordering = ["-created_at"]  # ordre par défaut : commandes les plus récentes en premier

    def get_queryset(self):
        return Order.objects.prefetch_related("items", "history").order_by("-created_at")

    def get_serializer_class(self):
        return OrderListSerializer if self.action == "list" else OrderSerializer

    @action(detail=True, methods=["get"])
    def invoice(self, request, number=None):
        """GET /api/v1/admin/orders/{number}/invoice/ — Facture côté admin."""
        order = self.get_object()
        try:
            inv = order.invoice
        except order.__class__.invoice.RelatedObjectDoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Facture non encore disponible.")
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["patch"], url_path="update")
    @transaction.atomic
    def update_order(self, request, number=None):
        order = self.get_object()
        s = AdminOrderUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "status" in d:
            order = change_status(order, d["status"], by=request.user, note=d.get("note", ""))
        fields = []
        if "payment_status" in d:
            new_ps = d["payment_status"]
            # Règle stricte : l'admin ne peut PAS marquer manuellement une commande comme payée
            if new_ps == Order.PaymentStatus.PAID:
                raise ValidationError(
                    {"payment_status": "Le statut PAID ne peut être défini que par un système de paiement vérifié. Contactez le support technique."}
                )
            # L'admin peut uniquement rembourser une commande déjà payée
            if new_ps == Order.PaymentStatus.REFUNDED and order.payment_status != Order.PaymentStatus.PAID:
                raise ValidationError(
                    {"payment_status": "Seule une commande déjà payée peut être remboursée."}
                )
            order.payment_status = new_ps
            fields.append("payment_status")
        if "tracking_info" in d:
            order.tracking_info = d["tracking_info"]
            fields.append("tracking_info")
        if "delivery_fee" in d:
            if not order.delivery_fee_pending:
                raise ValidationError({"delivery_fee": "Les frais sont deja fixes par la zone de livraison."})
            order.delivery_fee = d["delivery_fee"]
            order.total = order.subtotal + d["delivery_fee"]
            order.delivery_fee_pending = False
            fields += ["delivery_fee", "total", "delivery_fee_pending"]
        if fields:
            order.save(update_fields=fields + ["updated_at"])
        return Response(OrderSerializer(order).data)


class AdminDashboardView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        threshold = StoreSettings.load().low_stock_threshold
        orders = Order.objects.all()
        by = lambda *st: orders.filter(status__in=st).count()
        # CA : commandes payées, non annulées, non remboursées
        revenue = orders.filter(
            payment_status=Order.PaymentStatus.PAID
        ).exclude(
            status=Order.Status.CANCELLED
        ).exclude(
            payment_status=Order.PaymentStatus.REFUNDED
        ).aggregate(t=Sum("total"))["t"] or 0

        from apps.catalog.views import with_availability

        active = with_availability(Product.objects.filter(is_published=True, is_archived=False))
        top = (
            OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
            .values("product_name").annotate(sold=Sum("quantity")).order_by("-sold")[:5]
        )
        return Response({
            "orders_total": orders.count(),
            "orders_pending": by("pending"),
            "orders_in_progress": by("confirmed", "preparing", "shipped"),
            "orders_delivered": by("delivered"),
            "revenue_collected": revenue,
            "products_active": active.count(),
            "products_out_of_stock": active.filter(avail__lte=0).count(),
            "products_low_stock": active.filter(avail__gt=0, avail__lte=threshold).count(),
            "top_products": list(top),
        })
