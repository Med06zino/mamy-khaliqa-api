# -*- coding: utf-8 -*-
"""
Commande : python manage.py cleanup_categories

Nettoie les categories pour n'en conserver que deux :
  - Khaliqa Beauty  (slug : khaliqa-beauty)
  - Khaliqa Hair    (slug : khaliqa-hair)

Deplace tous les produits des autres categories vers l'une de ces deux categories
selon leur type (hair/beauty), puis supprime les categories inutiles.
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product


class Command(BaseCommand):
    help = "Nettoie les categories pour n'en conserver que Khaliqa Beauty et Khaliqa Hair"

    def handle(self, *args, **opts):
        self.stdout.write("Debut du nettoyage des categories...\n")

        # 1. S'assurer que les deux catégories principales existent
        beauty_cat, _ = Category.objects.get_or_create(
            slug="khaliqa-beauty",
            defaults={
                "name": "Khaliqa Beauty",
                "description": (
                    "Cosmétiques visage et lèvres : gloss, soins éclat, huile pousse-cils. "
                    "Produits pensés pour sublimer votre beauté au quotidien."
                ),
                "position": 1,
                "is_active": True,
            },
        )

        hair_cat, _ = Category.objects.get_or_create(
            slug="khaliqa-hair",
            defaults={
                "name": "Khaliqa Hair",
                "description": (
                    "Gamme capillaire complète : huiles nourrissantes, soins hydratants et "
                    "masques réparateurs pour des cheveux sains et brillants."
                ),
                "position": 2,
                "is_active": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(f"[OK] Categories principales pretes : {beauty_cat.name} (ID {beauty_cat.id}), {hair_cat.name} (ID {hair_cat.id})")
        )

        # 2. Identifier les catégories à supprimer (tout sauf les 2 principales)
        categories_to_delete = Category.objects.exclude(slug__in=["khaliqa-beauty", "khaliqa-hair"])

        if not categories_to_delete.exists():
            self.stdout.write(self.style.WARNING("Aucune categorie supplementaire a nettoyer."))
            return

        self.stdout.write(f"\n{categories_to_delete.count()} categorie(s) supplementaire(s) detectee(s) :")
        for cat in categories_to_delete:
            self.stdout.write(f"  - {cat.name} (slug: {cat.slug}, ID: {cat.id})")

        # 3. Déplacer les produits des catégories à supprimer
        products_moved = 0
        for cat in categories_to_delete:
            products = Product.objects.filter(category=cat)
            if products.exists():
                # Déterminer la catégorie cible basée sur le slug/nom
                cat_slug = cat.slug.lower()
                cat_name = cat.name.lower()

                if any(k in cat_slug or k in cat_name for k in ["hair", "capillaire", "cheveux", "pousse-cils", "cils"]):
                    target_cat = hair_cat
                else:
                    target_cat = beauty_cat

                # Déplacer les produits
                count = products.update(category=target_cat)
                products_moved += count
                self.stdout.write(
                    f"  -> {count} produit(s) deplace(s) vers {target_cat.name}"
                )

        if products_moved > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\n[OK] {products_moved} produit(s) deplace(s) avec succes")
            )

        # 4. Supprimer les catégories inutiles
        deleted_count = categories_to_delete.count()
        categories_to_delete.delete()

        self.stdout.write(
            self.style.SUCCESS(f"\n[OK] {deleted_count} categorie(s) supprimee(s)")
        )

        # 5. Résumé final
        all_cats = Category.objects.all()
        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Nettoyage termine. {all_cats.count()} categorie(s) restante(s) :"
        ))
        for cat in all_cats:
            product_count = Product.objects.filter(category=cat).count()
            self.stdout.write(f"  - {cat.name} : {product_count} produit(s)")
