"""Logique metier des commandes. Le serveur recalcule prix, stock et frais : rien n'est pris du navigateur."""
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Product, ProductVariant, StockMovement
from apps.deliveries.models import DeliveryZone

from .models import Order, OrderItem, OrderStatusHistory

TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.PREPARING, Order.Status.CANCELLED},
    Order.Status.PREPARING: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
}


def _merge_items(items):
    merged = {}
    for it in items:
        key = (it["product_id"], it.get("variant_id"))
        merged[key] = merged.get(key, 0) + it["quantity"]
    return merged


@transaction.atomic
def create_order(*, user, data, idempotency_key=None):
    if idempotency_key:
        existing = Order.objects.filter(idempotency_key=idempotency_key, user=user).first()
        if existing:
            return existing, False

    merged = _merge_items(data["items"])
    product_ids = sorted({pid for pid, _ in merged})
    products = {
        p.pk: p
        for p in Product.objects.select_for_update().public().filter(pk__in=product_ids)
    }
    variant_ids = sorted({vid for _, vid in merged if vid})
    variants = {
        v.pk: v
        for v in ProductVariant.objects.select_for_update().filter(pk__in=variant_ids, is_active=True)
    }

    lines, errors, subtotal = [], [], 0
    for (pid, vid), qty in merged.items():
        product = products.get(pid)
        if not product:
            errors.append(f"Un produit de votre panier n'est plus disponible (reference {pid}).")
            continue
        variant = None
        has_variants = product.variants.filter(is_active=True).exists()
        if vid:
            variant = variants.get(vid)
            if not variant or variant.product_id != pid:
                errors.append(f"La variante choisie pour « {product.name} » n'est plus disponible.")
                continue
        elif has_variants:
            errors.append(f"Choisissez une variante pour « {product.name} ».")
            continue
        available = variant.stock if variant else product.stock
        if qty > available:
            errors.append(f"Stock insuffisant pour « {product.name} » : {available} disponible(s).")
            continue
        unit = variant.effective_price if variant else product.price
        subtotal += unit * qty
        lines.append((product, variant, unit, qty))
    if errors:
        raise ValidationError({"items": errors})

    zone = None
    fee, fee_pending, zone_name = 0, False, ""
    if data.get("delivery_zone"):
        zone = DeliveryZone.objects.filter(pk=data["delivery_zone"], is_active=True).first()
        if not zone:
            raise ValidationError({"delivery_zone": "Zone de livraison inconnue."})
        fee, zone_name = zone.fee, zone.name
    else:
        fee_pending, zone_name = True, "Autre zone (frais a confirmer)"

    try:
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                idempotency_key=idempotency_key or None,
                source=data.get("source", Order.Source.WEB),
                first_name=data["first_name"], last_name=data["last_name"],
                email=data.get("email", ""), phone=data["phone"],
                address_line=data["address_line"], city=data.get("city", ""),
                delivery_zone=zone, delivery_zone_name=zone_name,
                customer_note=data.get("customer_note", ""),
                subtotal=subtotal, delivery_fee=fee, delivery_fee_pending=fee_pending,
                total=subtotal + fee,
            )
    except IntegrityError:  # double soumission concurrente avec la meme cle
        # Reconstruire la queryset selon que l'utilisateur est authentifie ou guest.
        if user is not None:
            return Order.objects.get(idempotency_key=idempotency_key, user=user), False
        else:
            return Order.objects.get(idempotency_key=idempotency_key, user__isnull=True), False

    for product, variant, unit, qty in lines:
        OrderItem.objects.create(
            order=order, product=product, variant=variant, product_name=product.name,
            product_sku=variant.sku if variant else product.sku,
            variant_name=variant.name if variant else "", unit_price=unit, quantity=qty,
        )
        target = variant or product
        target.stock -= qty
        target.save(update_fields=["stock"])
        StockMovement.objects.create(
            product=product, variant=variant, delta=-qty, reason=StockMovement.Reason.ORDER, reference=order.number
        )
    OrderStatusHistory.objects.create(order=order, status=order.status, note="Commande enregistree.")
    return order, True


@transaction.atomic
def change_status(order, new_status, *, by=None, note=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if new_status == order.status:
        return order
    if new_status not in TRANSITIONS[order.status]:
        raise ValidationError({"status": f"Passage impossible de « {order.get_status_display()} » vers « {Order.Status(new_status).label} »."})
    if new_status == Order.Status.CANCELLED:
        for item in order.items.select_related("product", "variant"):
            if item.product_id:
                target = item.variant or item.product
                target.stock += item.quantity
                target.save(update_fields=["stock"])
                StockMovement.objects.create(
                    product=item.product, variant=item.variant, delta=item.quantity,
                    reason=StockMovement.Reason.CANCEL, reference=order.number,
                )
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusHistory.objects.create(order=order, status=new_status, note=note, changed_by=by)
    return order
