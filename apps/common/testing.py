from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.deliveries.models import DeliveryZone


def make_user(email="client@test.sn", **kw):
    return User.objects.create_user(email=email, password="Motdepasse-Solide-42", first_name="Awa", last_name="Diop", **kw)


def make_staff():
    return User.objects.create_user(email="admin@test.sn", password="Motdepasse-Solide-42", is_staff=True)


def make_catalog():
    cat = Category.objects.create(name="Gloss")
    p = Product.objects.create(category=cat, name="Gloss Rose", sku="G-1", price=5000, stock=5, is_published=True)
    zone = DeliveryZone.objects.create(name="Dakar", fee=1500)
    return cat, p, zone


def client_for(user=None):
    c = APIClient()
    if user:
        c.force_login(user)
    return c


def order_payload(product, zone=None, qty=1, **extra):
    data = {
        "items": [{"product_id": product.pk, "quantity": qty}],
        "first_name": "Awa", "last_name": "Diop", "phone": "770000000",
        "address_line": "Rue 10", "city": "Dakar", "delivery_zone": zone.pk if zone else None,
    }
    data.update(extra)
    return data
