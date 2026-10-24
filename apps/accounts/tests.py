from django.test import TestCase

from apps.common.testing import client_for, make_staff, make_user


class AuthTests(TestCase):
    def test_register_login_logout(self):
        c = client_for()
        r = c.post("/api/v1/auth/register/", {
            "first_name": "A", "last_name": "B", "email": "A@Test.sn", "phone": "77", "password": "Motdepasse-Solide-42",
            "password_confirm": "Motdepasse-Solide-42", "accept_terms": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.get("/api/v1/auth/me/").json()["email"], "a@test.sn")
        self.assertEqual(c.post("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 403)
        r = c.post("/api/v1/auth/login/", {"email": "a@test.sn", "password": "Motdepasse-Solide-42"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_register_rejects_weak_or_mismatch(self):
        r = client_for().post("/api/v1/auth/register/", {
            "first_name": "A", "last_name": "B", "email": "x@test.sn", "phone": "77", "password": "12345678",
            "password_confirm": "12345678", "accept_terms": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_bad_login(self):
        make_user()
        r = client_for().post("/api/v1/auth/login/", {"email": "client@test.sn", "password": "nope"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_endpoints_forbidden_for_customers(self):
        customer = make_user()
        for path in ["/api/v1/admin/dashboard/", "/api/v1/admin/orders/", "/api/v1/admin/customers/", "/api/v1/admin/settings/"]:
            self.assertEqual(client_for(customer).get(path).status_code, 403, path)
            self.assertIn(client_for().get(path).status_code, (401, 403), path)
        self.assertEqual(client_for(make_staff()).get("/api/v1/admin/dashboard/").status_code, 200)

    def test_addresses_isolated(self):
        a, b = make_user("a@t.sn"), make_user("b@t.sn")
        ca = client_for(a)
        r = ca.post("/api/v1/addresses/", {"recipient_name": "A", "phone": "7", "line1": "x", "city": "y"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(client_for(b).get("/api/v1/addresses/").json(), [])
        self.assertEqual(client_for(b).delete(f"/api/v1/addresses/{r.json()['id']}/").status_code, 404)

    def test_password_reset_does_not_leak_accounts(self):
        make_user()
        c = client_for()
        r1 = c.post("/api/v1/auth/password-reset/", {"email": "client@test.sn"}, format="json")
        r2 = c.post("/api/v1/auth/password-reset/", {"email": "inconnu@test.sn"}, format="json")
        self.assertEqual(r1.json(), r2.json())


class AuthSessionTests(TestCase):
    """Tests sur la robustesse de la session et des corrections effectuées."""

    def test_logout_clears_session_and_blocks_access(self):
        """Après logout, /auth/me/ doit retourner 403 (session détruite)."""
        u = make_user()
        c = client_for(u)
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(c.post("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 403)

    def test_inactive_user_cannot_login(self):
        """Un compte désactivé (is_active=False) ne peut pas se connecter."""
        u = make_user("inactive@test.sn")
        u.is_active = False
        u.save()
        r = client_for().post(
            "/api/v1/auth/login/",
            {"email": "inactive@test.sn", "password": "Motdepasse-Solide-42"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_me_returns_correct_fields(self):
        """GET /auth/me/ renvoie les champs attendus — is_staff inclus."""
        u = make_user()
        data = client_for(u).get("/api/v1/auth/me/").json()
        for field in ("id", "email", "first_name", "last_name", "phone", "is_staff"):
            self.assertIn(field, data, f"Champ manquant : {field}")
        self.assertFalse(data["is_staff"])
        self.assertNotIn("password", data)

    def test_staff_me_exposes_is_staff_true(self):
        """Un staff voit is_staff=True dans /auth/me/."""
        data = client_for(make_staff()).get("/api/v1/auth/me/").json()
        self.assertTrue(data["is_staff"])

    def test_change_password_requires_correct_current(self):
        """Le changement de mot de passe rejette un mauvais mot de passe actuel."""
        u = make_user()
        r = client_for(u).post(
            "/api/v1/auth/change-password/",
            {"current_password": "MAUVAIS", "new_password": "NouveauPwd-Secure-99"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_change_password_updates_and_keeps_session(self):
        """Après changement de mot de passe, la session reste valide (re-login())."""
        u = make_user()
        c = client_for(u)
        r = c.post(
            "/api/v1/auth/change-password/",
            {"current_password": "Motdepasse-Solide-42", "new_password": "NouveauPwd-Secure-99"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        # La session doit toujours être valide après le changement
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 200)

    def test_register_normalises_email_to_lowercase(self):
        """L'e-mail est normalisé en minuscules à l'inscription."""
        r = client_for().post(
            "/api/v1/auth/register/",
            {
                "first_name": "Test", "last_name": "User",
                "email": "TestUser@EXAMPLE.SN", "phone": "77",
                "password": "Motdepasse-Solide-42",
                "password_confirm": "Motdepasse-Solide-42",
                "accept_terms": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["email"], "testuser@example.sn")

    def test_duplicate_email_register_rejected(self):
        """On ne peut pas créer deux comptes avec le même e-mail."""
        make_user()
        r = client_for().post(
            "/api/v1/auth/register/",
            {
                "first_name": "A", "last_name": "B",
                "email": "client@test.sn", "phone": "77",
                "password": "Motdepasse-Solide-42",
                "password_confirm": "Motdepasse-Solide-42",
                "accept_terms": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_seed_test_accounts_command_is_idempotent(self):
        """La commande seed_test_accounts peut être relancée sans doublon."""
        import os
        from unittest import mock
        from django.core.management import call_command
        with mock.patch.dict(os.environ, {"ALLOW_TEST_SEED": "1"}):
            call_command("seed_test_accounts", verbosity=0)
            from apps.accounts.models import User as UserModel
            count_first = UserModel.objects.count()
            call_command("seed_test_accounts", verbosity=0)
            self.assertEqual(UserModel.objects.count(), count_first)

    def test_seed_creates_admin_and_client_accounts(self):
        """Le seeder crée bien un compte staff et des comptes clients."""
        import os
        from unittest import mock
        from django.core.management import call_command
        with mock.patch.dict(os.environ, {"ALLOW_TEST_SEED": "1"}):
            call_command("seed_test_accounts", verbosity=0)
        from apps.accounts.models import User as UserModel
        self.assertTrue(UserModel.objects.filter(email="admin@dev.local", is_staff=True).exists())
        self.assertTrue(UserModel.objects.filter(email="client1@dev.local", is_staff=False).exists())
        self.assertTrue(UserModel.objects.filter(email="inactive@dev.local", is_active=False).exists())

    def test_seed_does_not_overwrite_existing_password(self):
        """Le seeder ne réinitialise pas le mot de passe si le compte existe."""
        import os
        from unittest import mock
        from django.core.management import call_command
        from apps.accounts.models import User as UserModel
        # Créer le compte avec un mot de passe différent
        u = UserModel.objects.create_user(
            email="admin@dev.local",
            password="AutreMdp-Solide-2099",
            is_staff=True,
        )
        with mock.patch.dict(os.environ, {"ALLOW_TEST_SEED": "1"}):
            call_command("seed_test_accounts", verbosity=0)
        u.refresh_from_db()
        # Le mot de passe AutreMdp-Solide-2099 doit toujours fonctionner
        from django.contrib.auth import authenticate
        self.assertIsNotNone(
            authenticate(request=None, username="admin@dev.local", password="AutreMdp-Solide-2099")
        )
