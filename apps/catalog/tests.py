from django.test import TestCase

from apps.catalog.models import Product, ProductVariant
from apps.common.testing import client_for, make_catalog, make_staff, make_user, order_payload


class CatalogTests(TestCase):
    def setUp(self):
        self.cat, self.p, self.zone = make_catalog()

    def test_listing_filters_and_hidden_products(self):
        Product.objects.create(category=self.cat, name="Cache", sku="H", price=1000, stock=1, is_published=False)
        Product.objects.create(category=self.cat, name="Epuise", sku="E", price=9000, stock=0, is_published=True)
        c = client_for()
        names = [x["name"] for x in c.get("/api/v1/products/").json()["results"]]
        self.assertIn("Gloss Rose", names)
        self.assertNotIn("Cache", names)
        self.assertEqual(len(c.get("/api/v1/products/?in_stock=true").json()["results"]), 1)
        self.assertEqual(len(c.get("/api/v1/products/?min_price=6000").json()["results"]), 1)
        self.assertEqual(len(c.get("/api/v1/products/?search=gloss").json()["results"]), 1)
        asc = [x["price"] for x in c.get("/api/v1/products/?ordering=price").json()["results"]]
        self.assertEqual(asc, sorted(asc))

    def test_has_promo_filter(self):
        """Seuls les produits avec compare_at_price sont retournés par ?has_promo=true."""
        promo = Product.objects.create(
            category=self.cat, name="Promo", sku="P-1",
            price=3000, compare_at_price=5000, stock=2, is_published=True,
        )
        r = client_for().get("/api/v1/products/?has_promo=true").json()
        names = [x["name"] for x in r["results"]]
        self.assertIn("Promo", names)
        self.assertNotIn("Gloss Rose", names)
        r2 = client_for().get("/api/v1/products/?has_promo=false").json()
        names2 = [x["name"] for x in r2["results"]]
        self.assertNotIn("Promo", names2)
        self.assertIn("Gloss Rose", names2)
        promo.delete()

    def test_detail_and_variants_stock(self):
        ProductVariant.objects.create(product=self.p, name="10 ml", sku="G-1-10", stock=3)
        d = client_for().get(f"/api/v1/products/{self.p.slug}/").json()
        self.assertEqual(d["available_stock"], 3)
        self.assertEqual(len(d["variants"]), 1)

    def test_is_featured_exposed_in_list(self):
        """Le champ is_featured est exposé dans la liste publique."""
        d = client_for().get(f"/api/v1/products/").json()["results"]
        self.assertIn("is_featured", d[0])
        self.assertFalse(d[0]["is_featured"])  # défaut False

    # ── best-sellers ──────────────────────────────────────────────

    def test_best_sellers_fallback_to_featured_when_no_sales(self):
        """Sans ventes, retourne les produits is_featured=True (fallback étape 2)."""
        self.p.is_featured = True
        self.p.save()
        r = client_for().get("/api/v1/products/best-sellers/").json()
        self.assertTrue(r["is_fallback"])
        self.assertEqual(len(r["results"]), 1)
        self.assertEqual(r["results"][0]["name"], "Gloss Rose")

    def test_best_sellers_fallback_to_recent_when_nothing_featured(self):
        """Sans ventes ni produit featured, retourne les plus récents."""
        r = client_for().get("/api/v1/products/best-sellers/").json()
        self.assertTrue(r["is_fallback"])
        self.assertEqual(r["results"][0]["name"], "Gloss Rose")

    def test_best_sellers_from_real_orders(self):
        """Avec des ventes réelles, retourne les vrais best-sellers (is_fallback=False)."""
        client_for().post("/api/v1/orders/", order_payload(self.p, self.zone, qty=2), format="json")
        r = client_for().get("/api/v1/products/best-sellers/").json()
        self.assertFalse(r["is_fallback"])
        self.assertEqual(r["results"][0]["name"], "Gloss Rose")

    # ── admin ─────────────────────────────────────────────────────

    def test_admin_product_crud_and_archive(self):
        staff = client_for(make_staff())
        r = staff.post(
            "/api/v1/admin/products/",
            {"category": self.cat.pk, "name": "Nouveau", "sku": "N-1", "price": 3000, "stock": 2},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("is_featured", r.json())  # champ bien exposé
        bad = staff.post(
            "/api/v1/admin/products/",
            {"category": self.cat.pk, "name": "X", "sku": "X-1", "price": 3000, "compare_at_price": 2000},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(staff.delete(f"/api/v1/admin/products/{r.json()['id']}/").status_code, 204)

    def test_admin_can_set_is_featured(self):
        """L'admin peut activer is_featured sur un produit."""
        staff = client_for(make_staff())
        r = staff.patch(
            f"/api/v1/admin/products/{self.p.pk}/", {"is_featured": True}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.p.refresh_from_db()
        self.assertTrue(self.p.is_featured)

    def test_customer_cannot_edit_products(self):
        r = client_for(make_user()).patch(
            f"/api/v1/admin/products/{self.p.pk}/", {"price": 1}, format="json"
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(client_for().post("/api/v1/products/", {}).status_code, 405)
