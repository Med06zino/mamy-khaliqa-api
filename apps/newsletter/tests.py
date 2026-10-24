from django.core.cache import cache
from django.test import TestCase

from apps.common.testing import client_for, make_staff

from .models import NewsletterSubscriber

URL = "/api/v1/newsletter/subscribe/"


class NewsletterSubscribeTests(TestCase):
    """
    Tests de l'endpoint newsletter.

    Le throttle DRF (ScopedRateThrottle) s'appuie sur le cache Django.
    On vide le cache dans setUp() pour garantir l'isolation entre tests,
    sans avoir à désactiver le throttle via override_settings (ce qui ne
    purge pas le cache en mémoire déjà rempli par les tests précédents).
    """

    def setUp(self):
        # Vide le cache entre chaque test pour éviter les faux 429
        cache.clear()

    def test_new_subscriber_is_created(self):
        r = client_for().post(URL, {"email": "awa@test.sn"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        self.assertTrue(NewsletterSubscriber.objects.get(email="awa@test.sn").is_active)

    def test_email_is_normalised_to_lowercase(self):
        client_for().post(URL, {"email": "AWA@TEST.SN"}, format="json")
        self.assertTrue(NewsletterSubscriber.objects.filter(email="awa@test.sn").exists())

    def test_duplicate_does_not_create_second_row(self):
        client_for().post(URL, {"email": "awa@test.sn"}, format="json")
        r2 = client_for().post(URL, {"email": "awa@test.sn"}, format="json")
        self.assertEqual(r2.status_code, 200)  # 200, pas 201
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)

    def test_reactivates_inactive_subscriber(self):
        """Un abonné désactivé est réactivé sans créer de doublon."""
        sub = NewsletterSubscriber.objects.create(email="reactiver@test.sn", is_active=False)
        r = client_for().post(URL, {"email": "reactiver@test.sn"}, format="json")
        self.assertEqual(r.status_code, 200)
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)

    def test_invalid_email_rejected(self):
        r = client_for().post(URL, {"email": "pas-un-email"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)

    def test_admin_can_list_subscribers(self):
        NewsletterSubscriber.objects.create(email="a@test.sn")
        NewsletterSubscriber.objects.create(email="b@test.sn")
        r = client_for(make_staff()).get("/api/v1/admin/newsletter/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)

    def test_anonymous_cannot_list_subscribers(self):
        self.assertEqual(client_for().get("/api/v1/admin/newsletter/").status_code, 403)

    def test_admin_can_deactivate_subscriber(self):
        sub = NewsletterSubscriber.objects.create(email="awa@test.sn")
        r = client_for(make_staff()).patch(
            f"/api/v1/admin/newsletter/{sub.pk}/", {"is_active": False}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        sub.refresh_from_db()
        self.assertFalse(sub.is_active)
