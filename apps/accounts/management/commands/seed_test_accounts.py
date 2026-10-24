"""
Commande : python manage.py seed_test_accounts

Crée des comptes de démonstration pour le développement et les tests QA.

RÈGLES DE SÉCURITÉ :
  - Bloquée en production (DEBUG=False) sauf si ALLOW_TEST_SEED=1 est positionné.
  - Idempotente : peut être relancée sans créer de doublons.
  - N'écrase JAMAIS un mot de passe existant pour les comptes déjà créés.
  - Les comptes créés ont l'e-mail suffixé par @dev.local (hors périmètre production).

Comptes créés :
  Rôle         | E-mail                    | Mot de passe
  -------------|---------------------------|---------------------------
  Superadmin   | superadmin@dev.local      | Dev!SuperAdmin2024#
  Staff/admin  | admin@dev.local           | Dev!Admin2024#
  Client test  | client1@dev.local         | Dev!Client2024#
  Client test  | client2@dev.local         | Dev!Client2024#
  Client inactif| inactive@dev.local       | Dev!Client2024#
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


# ── Définition des comptes de test ────────────────────────────────────────────

TEST_ACCOUNTS = [
    {
        "email":      "superadmin@dev.local",
        "password":   "Dev!SuperAdmin2024#",
        "first_name": "Super",
        "last_name":  "Admin",
        "phone":      "221700000001",
        "is_staff":   True,
        "is_superuser": True,
        "is_active":  True,
        "role_label": "Superadmin",
    },
    {
        "email":      "admin@dev.local",
        "password":   "Dev!Admin2024#",
        "first_name": "Fatou",
        "last_name":  "Ndiaye",
        "phone":      "221700000002",
        "is_staff":   True,
        "is_superuser": False,
        "is_active":  True,
        "role_label": "Staff (admin boutique)",
    },
    {
        "email":      "client1@dev.local",
        "password":   "Dev!Client2024#",
        "first_name": "Awa",
        "last_name":  "Diop",
        "phone":      "221700000003",
        "is_staff":   False,
        "is_superuser": False,
        "is_active":  True,
        "role_label": "Cliente active",
    },
    {
        "email":      "client2@dev.local",
        "password":   "Dev!Client2024#",
        "first_name": "Aïda",
        "last_name":  "Fall",
        "phone":      "221700000004",
        "is_staff":   False,
        "is_superuser": False,
        "is_active":  True,
        "role_label": "Cliente active (2)",
    },
    {
        "email":      "inactive@dev.local",
        "password":   "Dev!Client2024#",
        "first_name": "Rokhaya",
        "last_name":  "Sall",
        "phone":      "221700000005",
        "is_staff":   False,
        "is_superuser": False,
        "is_active":  False,
        "role_label": "Cliente désactivée (test accès refusé)",
    },
]


class Command(BaseCommand):
    help = (
        "Crée des comptes de démonstration pour le développement. "
        "Bloquée en production. Idempotente (sans écrasement de mot de passe)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force la création même si DEBUG=False (requiert ALLOW_TEST_SEED=1).",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Réinitialise les mots de passe des comptes existants (dev only).",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Affiche les comptes de test sans rien créer.",
        )

    def handle(self, *args, **opts):  # noqa: C901
        # ── Vérification de sécurité ───────────────────────────────────────────
        if not settings.DEBUG and not os.environ.get("ALLOW_TEST_SEED"):
            raise CommandError(
                "Cette commande est bloquée en production. "
                "Positionnez ALLOW_TEST_SEED=1 si vous savez ce que vous faites."
            )

        # ── Mode liste seul ────────────────────────────────────────────────────
        if opts["list"]:
            self.stdout.write(self.style.HTTP_INFO("\nComptes de test disponibles :\n"))
            for acc in TEST_ACCOUNTS:
                status_mark = "actif" if acc["is_active"] else "INACTIF"
                role = "STAFF" if acc["is_staff"] else "client"
                self.stdout.write(
                    f"  [{role.upper():6}] {acc['email']:30}  pwd: {acc['password']}  "
                    f"({acc['role_label']})  [{status_mark}]"
                )
            return

        # ── Création / mise à jour ─────────────────────────────────────────────
        created_count  = 0
        updated_count  = 0
        skipped_count  = 0

        for acc in TEST_ACCOUNTS:
            email = acc["email"].lower()
            existing = User.objects.filter(email=email).first()

            if existing:
                # Mise à jour des métadonnées (nom, phone, flags) sans toucher au mdp
                changed = False
                for field in ("first_name", "last_name", "phone", "is_staff", "is_superuser", "is_active"):
                    if getattr(existing, field) != acc[field]:
                        setattr(existing, field, acc[field])
                        changed = True

                if opts["reset_passwords"]:
                    existing.set_password(acc["password"])
                    changed = True
                    self.stdout.write(
                        self.style.WARNING(f"  [RESET] Mot de passe reinitialise : {email}")
                    )

                if changed:
                    existing.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"  [MAJ] {email}  ({acc['role_label']})")
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(f"  [OK]  {email}")
            else:
                # Création
                user = User.objects.create_user(
                    email=email,
                    password=acc["password"],
                    first_name=acc["first_name"],
                    last_name=acc["last_name"],
                    phone=acc["phone"],
                    is_staff=acc["is_staff"],
                    is_superuser=acc["is_superuser"],
                    is_active=acc["is_active"],
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [CRE] {user.email:30}  ({acc['role_label']})")
                )

        # ── Résumé ─────────────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé — {created_count} créé(s), "
                f"{updated_count} mis à jour, "
                f"{skipped_count} inchangé(s)."
            )
        )
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Comptes disponibles pour tester :"))
        self.stdout.write("")
        for acc in TEST_ACCOUNTS:
            role = "ADMIN " if acc["is_staff"] else "client"
            flag = "" if acc["is_active"] else "  [INACTIF]"
            self.stdout.write(
                f"  [{role.upper():6}]  {acc['email']:30}  {acc['password']}{flag}"
            )
        self.stdout.write("")
        self.stdout.write(
            "  Admin Django : http://127.0.0.1:8000/django-admin/"
        )
        self.stdout.write(
            "  API Swagger  : http://127.0.0.1:8000/api/docs/"
        )
