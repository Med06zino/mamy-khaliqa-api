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
