from django.test import TestCase

from apps.common.testing import client_for, make_staff

from .models import Banner


def make_banner(banner_type="hero", title="Hero test", is_active=True, position=0):
    return Banner.objects.create(
        banner_type=banner_type, title=title, is_active=is_active, position=position,
        button_text="Voir la boutique", link_url="/boutique",
    )


class BannerPublicTests(TestCase):
    def test_only_active_banners_are_exposed(self):
        make_banner(title="Active")
        make_banner(title="Inactive", is_active=False)
        r = client_for().get("/api/v1/banners/")
        self.assertEqual(r.status_code, 200)
        titles = [b["title"] for b in r.json()]
        self.assertIn("Active", titles)
        self.assertNotIn("Inactive", titles)

    def test_filter_by_type(self):
        make_banner(banner_type="hero", title="Hero")
        make_banner(banner_type="promo", title="Promo")
        heroes = client_for().get("/api/v1/banners/?banner_type=hero").json()
        self.assertTrue(all(b["banner_type"] == "hero" for b in heroes))
        promos = client_for().get("/api/v1/banners/?banner_type=promo").json()
        self.assertTrue(all(b["banner_type"] == "promo" for b in promos))

    def test_ordering_by_position(self):
        make_banner(title="Third", position=2)
        make_banner(title="First",  position=0)
        make_banner(title="Second", position=1)
        titles = [b["title"] for b in client_for().get("/api/v1/banners/").json()]
        self.assertEqual(titles, ["First", "Second", "Third"])

    def test_no_pagination(self):
        """Les bannières ne doivent pas être paginées (liste complète)."""
        for i in range(15):
            make_banner(title=f"Banner {i}")
        r = client_for().get("/api/v1/banners/")
        self.assertIsInstance(r.json(), list)  # pas un objet paginé {count, results}
        self.assertEqual(len(r.json()), 15)


class BannerAdminTests(TestCase):
    def setUp(self):
        self.staff = client_for(make_staff())

    def test_admin_can_create_banner(self):
        r = self.staff.post("/api/v1/admin/banners/", {
            "banner_type": "hero", "title": "Nouveau hero",
            "button_text": "Découvrir", "link_url": "/boutique",
            "position": 0, "is_active": True,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Banner.objects.count(), 1)

    def test_admin_can_deactivate_banner(self):
        b = make_banner()
        r = self.staff.patch(f"/api/v1/admin/banners/{b.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertFalse(b.is_active)

    def test_anonymous_cannot_access_admin_banners(self):
        self.assertEqual(client_for().get("/api/v1/admin/banners/").status_code, 403)
