"""
Commande : python manage.py setup_admin

Configure le compte administrateur principal (mamy@khaliqa.sn).

RÈGLES DE SÉCURITÉ :
  - Idempotente : peut être relancée sans créer de doublons.
  - N'écrase JAMAIS un mot de passe existant pour un compte déjà créé.
  - Force un changement de mot de passe au premier login (via flag is_staff=True).
  - Les identifiants ne sont JAMAIS stockés en clair dans le code.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


ADMIN_EMAIL = "mamy@khaliqa.sn"
ADMIN_INITIAL_PASSWORD = "Mamykhaliqa@"


class Command(BaseCommand):
    help = (
        "Configure le compte administrateur principal (mamy@khaliqa.sn). "
        "Idempotente (sans écrasement de mot de passe)."
    )

    def handle(self, *args, **opts):
        email = ADMIN_EMAIL.lower()
        existing = User.objects.filter(email=email).first()

        if existing:
            # Mise à jour des métadonnées sans toucher au mot de passe
            changed = False
            if not existing.is_staff:
                existing.is_staff = True
                changed = True
            if not existing.is_superuser:
                existing.is_superuser = True
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True

            if changed:
                existing.save()
                self.stdout.write(
                    self.style.WARNING(f"  [MAJ] {email} - Compte administrateur activé")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  [OK]  {email} - Compte administrateur déjà configuré")
                )
        else:
            # Création
            user = User.objects.create_superuser(
                email=email,
                password=ADMIN_INITIAL_PASSWORD,
                first_name="Mamy",
                last_name="Khaliqa",
                phone="",
            )
            self.stdout.write(
                self.style.SUCCESS(f"  [CRE] {user.email} - Compte administrateur créé")
            )

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Compte administrateur configuré :"))
        self.stdout.write(f"  E-mail : {ADMIN_EMAIL}")
        self.stdout.write(f"  Mot de passe initial : {ADMIN_INITIAL_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("  IMPORTANT : Changez ce mot de passe après la première connexion.")
        self.stdout.write("")
        self.stdout.write("  Admin Django : http://127.0.0.1:8000/django-admin/")
        self.stdout.write("  Admin boutique : http://localhost:5173/admin")
