from django.test import TestCase

from apps.catalog.models import Product, ProductVariant
from apps.common.testing import client_for, make_catalog, make_staff


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

    def test_detail_and_variants_stock(self):
        ProductVariant.objects.create(product=self.p, name="10 ml", sku="G-1-10", stock=3)
        d = client_for().get(f"/api/v1/products/{self.p.slug}/").json()
        self.assertEqual(d["available_stock"], 3)
        self.assertEqual(len(d["variants"]), 1)

    def test_no_best_sellers_without_sales(self):
        self.assertEqual(client_for().get("/api/v1/products/best-sellers/").json(), [])

    def test_admin_product_crud_and_archive(self):
        staff = client_for(make_staff())
        r = staff.post("/api/v1/admin/products/", {"category": self.cat.pk, "name": "Nouveau", "sku": "N-1", "price": 3000, "stock": 2}, format="json")
        self.assertEqual(r.status_code, 201)
        bad = staff.post("/api/v1/admin/products/", {"category": self.cat.pk, "name": "X", "sku": "X-1", "price": 3000, "compare_at_price": 2000}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(staff.delete(f"/api/v1/admin/products/{r.json()['id']}/").status_code, 204)

    def test_customer_cannot_edit_products(self):
        from apps.common.testing import make_user

        r = client_for(make_user()).patch(f"/api/v1/admin/products/{self.p.pk}/", {"price": 1}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(client_for().post("/api/v1/products/", {}).status_code, 405)
