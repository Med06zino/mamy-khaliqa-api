from django.test import TestCase, TransactionTestCase

from apps.catalog.models import Product, ProductVariant
from apps.common.testing import client_for, make_catalog, make_staff, make_user, order_payload
from apps.orders.models import Order


class OrderTests(TestCase):
    def setUp(self):
        self.cat, self.p, self.zone = make_catalog()

    def test_prices_recomputed_server_side(self):
        data = order_payload(self.p, self.zone, qty=2, subtotal=1, total=1, unit_price=1)
        r = client_for().post("/api/v1/orders/", data, format="json")
        self.assertEqual(r.status_code, 201)
        j = r.json()
        self.assertEqual((j["subtotal"], j["delivery_fee"], j["total"]), (10000, 1500, 11500))
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 3)
        self.assertTrue(j["number"].startswith("MK-"))

    def test_stock_cannot_be_exceeded(self):
        r = client_for().post("/api/v1/orders/", order_payload(self.p, self.zone, qty=6), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_unknown_zone_never_invents_fee(self):
        r = client_for().post("/api/v1/orders/", order_payload(self.p, None), format="json").json()
        self.assertTrue(r["delivery_fee_pending"])
        self.assertEqual(r["delivery_fee"], 0)

    def test_variant_required_and_priced(self):
        v = ProductVariant.objects.create(product=self.p, name="30 ml", sku="V1", price=7000, stock=2)
        r = client_for().post("/api/v1/orders/", order_payload(self.p, self.zone), format="json")
        self.assertEqual(r.status_code, 400)
        payload = order_payload(self.p, self.zone)
        payload["items"][0]["variant_id"] = v.pk
        r = client_for().post("/api/v1/orders/", payload, format="json")
        self.assertEqual(r.json()["subtotal"], 7000)
        v.refresh_from_db()
        self.assertEqual(v.stock, 1)

    def test_idempotency_prevents_duplicates(self):
        c = client_for()
        h = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}
        r1 = c.post("/api/v1/orders/", order_payload(self.p, self.zone), format="json", **h)
        r2 = c.post("/api/v1/orders/", order_payload(self.p, self.zone), format="json", **h)
        self.assertEqual(r1.json()["number"], r2.json()["number"])
        self.assertEqual(Order.objects.count(), 1)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 4)

    def test_orders_isolated_between_customers(self):
        a, b = make_user("a@t.sn"), make_user("b@t.sn")
        num = client_for(a).post("/api/v1/orders/", order_payload(self.p, self.zone), format="json").json()["number"]
        self.assertEqual(len(client_for(a).get("/api/v1/orders/").json()["results"]), 1)
        self.assertEqual(client_for(b).get("/api/v1/orders/").json()["results"], [])
        self.assertEqual(client_for(b).get(f"/api/v1/orders/{num}/").status_code, 404)
        self.assertEqual(client_for(b).post(f"/api/v1/orders/{num}/cancel/").status_code, 404)
        self.assertEqual(client_for().get("/api/v1/orders/").status_code, 403)

    def test_cancel_restores_stock_and_records_history(self):
        u = make_user()
        c = client_for(u)
        num = c.post("/api/v1/orders/", order_payload(self.p, self.zone, qty=2), format="json").json()["number"]
        r = c.post(f"/api/v1/orders/{num}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 5)
        self.assertEqual([h["status"] for h in r.json()["history"]], ["pending", "cancelled"])

    def test_admin_status_flow_and_invalid_transition(self):
        num = client_for().post("/api/v1/orders/", order_payload(self.p, self.zone), format="json").json()["number"]
        s = client_for(make_staff())
        url = f"/api/v1/admin/orders/{num}/update/"
        self.assertEqual(s.patch(url, {"status": "delivered"}, format="json").status_code, 400)
        self.assertEqual(s.patch(url, {"status": "confirmed", "tracking_info": "Livreur: Moussa"}, format="json").status_code, 200)
        self.assertEqual(s.patch(url, {"payment_status": "paid"}, format="json").json()["payment_status"], "paid")
        dash = s.get("/api/v1/admin/dashboard/").json()
        self.assertEqual((dash["orders_total"], dash["revenue_collected"]), (1, 6500))

    def test_guest_checkout_can_be_disabled(self):
        from apps.store_settings.models import StoreSettings

        s = StoreSettings.load()
        s.guest_checkout_enabled = False
        s.save()
        self.assertEqual(client_for().post("/api/v1/orders/", order_payload(self.p, self.zone), format="json").status_code, 403)
        self.assertEqual(client_for(make_user()).post("/api/v1/orders/", order_payload(self.p, self.zone), format="json").status_code, 201)

    def test_best_sellers_from_real_orders(self):
        client_for().post("/api/v1/orders/", order_payload(self.p, self.zone, qty=2), format="json")
        r = client_for().get("/api/v1/products/best-sellers/").json()
        self.assertFalse(r["is_fallback"])
        self.assertEqual([x["name"] for x in r["results"]], ["Gloss Rose"])


class PaymentTests(TestCase):
    """Tests des règles métier liées aux paiements et remboursements."""

    def setUp(self):
        self.cat, self.p, self.zone = make_catalog()

    def _create_order(self, **extra):
        """Crée une commande et retourne son numéro."""
        return client_for().post(
            "/api/v1/orders/",
            order_payload(self.p, self.zone, **extra),
            format="json",
        ).json()["number"]

    def _advance_to(self, staff_client, num, *statuses):
        """Fait avancer une commande à travers une liste de statuts."""
        for st in statuses:
            r = staff_client.patch(
                f"/api/v1/admin/orders/{num}/update/",
                {"status": st},
                format="json",
            )
            self.assertEqual(r.status_code, 200, f"Transition vers '{st}' échouée : {r.json()}")

    # ── payment_method tracé à la création ──────────────────────

    def test_payment_method_stored_on_create(self):
        """payment_method=cash_on_delivery est stocké et renvoyé dans la réponse."""
        data = order_payload(self.p, self.zone)
        data["payment_method"] = "cash_on_delivery"
        r = client_for().post("/api/v1/orders/", data, format="json")
        self.assertEqual(r.status_code, 201)
        j = r.json()
        self.assertEqual(j["payment_method"], "cash_on_delivery")
        self.assertEqual(j["payment_method_label"], "Paiement à la livraison")

    def test_payment_method_empty_by_default(self):
        """Sans payment_method explicite, le champ est vide et le label générique."""
        j = client_for().post(
            "/api/v1/orders/", order_payload(self.p, self.zone), format="json"
        ).json()
        self.assertEqual(j["payment_method"], "")
        self.assertEqual(j["payment_method_label"], "Non précisée")

    def test_payment_method_does_not_affect_payment_status(self):
        """Envoyer cash_on_delivery ne marque PAS la commande comme payée automatiquement."""
        data = order_payload(self.p, self.zone)
        data["payment_method"] = "cash_on_delivery"
        j = client_for().post("/api/v1/orders/", data, format="json").json()
        self.assertEqual(j["payment_status"], "unpaid")

    # ── Règles de marquage paid / refunded ──────────────────────

    def test_admin_can_mark_paid(self):
        """L'admin peut marquer une commande comme payée."""
        num = self._create_order()
        s = client_for(make_staff())
        r = s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "paid"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["payment_status"], "paid")

    def test_cannot_mark_paid_a_cancelled_order(self):
        """On ne peut pas marquer payée une commande annulée."""
        u = make_user()
        num = client_for(u).post(
            "/api/v1/orders/", order_payload(self.p, self.zone), format="json"
        ).json()["number"]
        client_for(u).post(f"/api/v1/orders/{num}/cancel/")
        s = client_for(make_staff())
        r = s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "paid"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_can_refund_a_paid_order(self):
        """L'admin peut rembourser une commande déjà payée."""
        num = self._create_order()
        s = client_for(make_staff())
        s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "paid"}, format="json")
        r = s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "refunded"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["payment_status"], "refunded")

    def test_cannot_refund_an_unpaid_order(self):
        """On ne peut pas rembourser une commande qui n'a pas encore été payée."""
        num = self._create_order()
        s = client_for(make_staff())
        r = s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "refunded"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("payment_status", r.json().get("errors", {}))

    def test_refunded_order_excluded_from_revenue(self):
        """Une commande remboursée n'est pas comptée dans le CA."""
        num = self._create_order()
        s = client_for(make_staff())
        # Payer puis rembourser
        s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "paid"},     format="json")
        s.patch(f"/api/v1/admin/orders/{num}/update/", {"payment_status": "refunded"}, format="json")
        dash = s.get("/api/v1/admin/dashboard/").json()
        # Le CA ne doit pas inclure cette commande remboursée
        self.assertEqual(dash["revenue_collected"], 0)

    def test_client_cannot_modify_payment_status(self):
        """Un client ne peut pas modifier le statut de paiement de sa commande."""
        u = make_user()
        c = client_for(u)
        num = c.post("/api/v1/orders/", order_payload(self.p, self.zone), format="json").json()["number"]
        # La route /orders/<number>/update/ n'existe pas côté client — on vérifie le 404/405
        r = c.patch(f"/api/v1/orders/{num}/update/", {"payment_status": "paid"}, format="json")
        self.assertIn(r.status_code, [404, 405])

    def test_order_response_contains_payment_method_label(self):
        """La réponse de la liste commandes contient payment_method."""
        u = make_user()
        c = client_for(u)
        data = order_payload(self.p, self.zone)
        data["payment_method"] = "cash_on_delivery"
        c.post("/api/v1/orders/", data, format="json")
        results = c.get("/api/v1/orders/").json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payment_method"], "cash_on_delivery")


class ReviewTests(TestCase):
    def test_only_verified_buyers_and_moderation(self):
        _, p, zone = make_catalog()
        u = make_user()
        c = client_for(u)
        body = {"product": p.pk, "rating": 5, "comment": "Super"}
        self.assertEqual(c.post("/api/v1/reviews/", body, format="json").status_code, 400)
        num = c.post("/api/v1/orders/", order_payload(p, zone), format="json").json()["number"]
        staff = client_for(make_staff())
        for st in ["confirmed", "preparing", "shipped", "delivered"]:
            staff.patch(f"/api/v1/admin/orders/{num}/update/", {"status": st}, format="json")
        self.assertEqual(c.post("/api/v1/reviews/", body, format="json").status_code, 201)
        self.assertEqual(client_for().get("/api/v1/reviews/").json()["results"], [])  # non approuve
        rid = staff.get("/api/v1/admin/reviews/").json()["results"][0]["id"]
        staff.patch(f"/api/v1/admin/reviews/{rid}/", {"is_approved": True}, format="json")
        public = client_for()
        self.assertEqual(len(public.get("/api/v1/reviews/").json()["results"]), 1)
        self.assertEqual(len(public.get(f"/api/v1/reviews/?product={p.slug}").json()["results"]), 1)
        other = Product.objects.create(
            category=p.category, name="Autre", sku="G-2", price=4000, stock=2, is_published=True
        )
        self.assertEqual(public.get(f"/api/v1/reviews/?product={other.slug}").json()["results"], [])

    def test_product_detail_exposes_review_eligibility(self):
        _, p, zone = make_catalog()
        u = make_user()
        c = client_for(u)
        self.assertFalse(c.get(f"/api/v1/products/{p.slug}/").json()["user_can_review"])
        num = c.post("/api/v1/orders/", order_payload(p, zone), format="json").json()["number"]
        staff = client_for(make_staff())
        for st in ["confirmed", "preparing", "shipped", "delivered"]:
            staff.patch(f"/api/v1/admin/orders/{num}/update/", {"status": st}, format="json")
        detail = c.get(f"/api/v1/products/{p.slug}/").json()
        self.assertTrue(detail["user_can_review"])
        item = staff.get(f"/api/v1/admin/orders/{num}/").json()
        self.assertEqual(item["allowed_transitions"], [])
        self.assertEqual(item["items"][0]["product_slug"], p.slug)
        c.post("/api/v1/reviews/", {"product": p.pk, "rating": 4, "comment": "Bien"}, format="json")
        self.assertFalse(c.get(f"/api/v1/products/{p.slug}/").json()["user_can_review"])


class ContactAndSettingsTests(TestCase):
    def test_contact_and_public_settings(self):
        r = client_for().post("/api/v1/contact/", {"name": "A", "email": "a@t.sn", "subject": "Hello", "message": "Bonjour"}, format="json")
        self.assertEqual(r.status_code, 201)
        pub = client_for().get("/api/v1/settings/").json()
        self.assertNotIn("low_stock_threshold", pub)
        s = client_for(make_staff())
        r = s.patch("/api/v1/admin/settings/", {"whatsapp_number": "+221 77 000 00 00"}, format="json")
        self.assertEqual(r.json()["whatsapp_number"], "221770000000")
        self.assertEqual(s.patch("/api/v1/admin/settings/", {"whatsapp_number": "abc"}, format="json").status_code, 400)
