import hashlib
import hmac
import json
import time
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product
from apps.deliveries.models import DeliveryZone
from apps.orders.models import Order, OrderItem, Payment
from apps.payments.models import PaymentWebhookLog, WaveCheckoutSession


class WavePaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cat = Category.objects.create(name="Beauty", slug="beauty")
        self.zone = DeliveryZone.objects.create(name="Dakar", fee=1500)
        self.product = Product.objects.create(
            category=self.cat, name="Gloss", sku="GLOSS-01", price=5000, stock=10, is_published=True
        )
        self.order = Order.objects.create(
            first_name="Awa",
            last_name="Diop",
            phone="221770000000",
            address_line="Mermoz",
            delivery_zone=self.zone,
            subtotal=5000,
            delivery_fee=1500,
            total=6500,
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.UNPAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            unit_price=5000,
            quantity=1,
        )

    def test_create_wave_checkout_session(self):
        """Tester l'initialisation de session Wave Checkout."""
        url = f"/api/v1/payments/{self.order.number}/wave/create/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("checkout_url", data)
        self.assertIn("session_id", data)
        self.assertEqual(data["amount"], 6500)

        # Vérifier l'enregistrement en base
        session = WaveCheckoutSession.objects.get(order=self.order)
        self.assertEqual(session.status, WaveCheckoutSession.Status.PENDING)

    @patch("apps.payments.services.send_admin_order_notification")
    def test_wave_webhook_successful_payment(self, mock_notify):
        """Tester la validation automatique de la commande via Webhook Wave."""
        # Créer d'abord la session
        session = WaveCheckoutSession.objects.create(
            order=self.order,
            session_id="cos_test_123",
            checkout_url="https://pay.wave.com/c/cos_test_123",
            amount=6500,
            status=WaveCheckoutSession.Status.PENDING,
        )

        secret = "test_wave_secret_key"
        payload = {
            "id": "evt_test_completed_1",
            "type": "checkout.session.completed",
            "data": {
                "id": "cos_test_123",
                "amount": "6500",
                "currency": "XOF",
                "client_reference": self.order.number,
                "transaction_id": "txn_wave_999",
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))

        signed_content = f"{timestamp}.".encode("utf-8") + raw_body
        signature = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
        signature_header = f"t={timestamp},v1={signature}"

        with self.settings(WAVE_WEBHOOK_SECRET=secret):
            response = self.client.post(
                "/api/v1/payments/wave/webhook/",
                data=raw_body,
                content_type="application/json",
                HTTP_WAVE_SIGNATURE=signature_header,
            )

        self.assertEqual(response.status_code, 200)

        # Vérifier que la commande est passée à PAID et CONFIRMED
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.order.payment_method, "wave")

        # Vérifier que le modèle Payment a été mis à jour
        payment = Payment.objects.get(order=self.order, provider="wave")
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.amount, 6500)

        # Vérifier que la notification admin a été déclenchée !
        mock_notify.assert_called_once_with(self.order, provider="Wave")

    def test_wave_webhook_rejects_invalid_signature(self):
        """Tester le rejet d'un webhook avec mauvaise signature."""
        payload = {"id": "evt_fraud", "type": "checkout.session.completed"}
        raw_body = json.dumps(payload).encode("utf-8")
        signature_header = f"t={int(time.time())},v1=invalidsignature123"

        with self.settings(WAVE_WEBHOOK_SECRET="secret"):
            response = self.client.post(
                "/api/v1/payments/wave/webhook/",
                data=raw_body,
                content_type="application/json",
                HTTP_WAVE_SIGNATURE=signature_header,
            )
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)
