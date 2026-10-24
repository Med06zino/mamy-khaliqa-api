"""
Commande : python manage.py seed_universes

Crée (ou met à jour si existants) les deux univers :
  - Khaliqa Beauty  (slug : khaliqa-beauty)
  - Khaliqa Hair    (slug : khaliqa-hair)

Idempotente : peut être relancée sans risque de doublon.
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category
from apps.store_settings.models import StoreSettings

UNIVERSES = [
    {
        "name": "Khaliqa Beauty",
        "slug": "khaliqa-beauty",
        "description": (
            "Cosmétiques visage et lèvres : gloss, soins éclat, huile pousse-cils. "
            "Produits pensés pour sublimer votre beauté au quotidien."
        ),
        "position": 1,
    },
    {
        "name": "Khaliqa Hair",
        "slug": "khaliqa-hair",
        "description": (
            "Gamme capillaire complète : huiles nourrissantes, soins hydratants et "
            "masques réparateurs pour des cheveux sains et brillants."
        ),
        "position": 2,
    },
]


class Command(BaseCommand):
    help = "Crée les catégories Khaliqa Beauty et Khaliqa Hair si elles n'existent pas."

    def handle(self, *args, **opts):
        # S'assurer que les paramètres de la boutique existent (singleton)
        StoreSettings.load()

        for data in UNIVERSES:
            # On tente d'abord par slug pour éviter les conflits de nom
            cat, created = Category.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name":        data["name"],
                    "description": data["description"],
                    "position":    data["position"],
                    "is_active":   True,
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Catégorie créée : {cat.name}  (slug: {cat.slug})")
                )
            else:
                # Mise à jour si le nom ou la description a changé
                updated = False
                if cat.name != data["name"]:
                    cat.name = data["name"]
                    updated = True
                if not cat.description:
                    cat.description = data["description"]
                    updated = True
                if cat.position != data["position"]:
                    cat.position = data["position"]
                    updated = True
                if not cat.is_active:
                    cat.is_active = True
                    updated = True
                if updated:
                    cat.save()
                    self.stdout.write(
                        self.style.WARNING(f"  ↺ Catégorie mise à jour : {cat.name}")
                    )
                else:
                    self.stdout.write(f"  — Déjà présente : {cat.name}")

        self.stdout.write(self.style.SUCCESS(
            "\nLes deux univers sont prêts.\n"
            "Accédez à http://127.0.0.1:8000/django-admin/catalog/category/ "
            "pour les voir, et à http://127.0.0.1:8000/django-admin/catalog/product/add/ "
            "pour ajouter vos premiers produits."
        ))
