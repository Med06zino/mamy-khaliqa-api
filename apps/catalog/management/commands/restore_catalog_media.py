from django.core.management.base import BaseCommand
from django.db import transaction
from apps.catalog.models import Category, Product, ProductImage
from apps.store_settings.models import StoreSettings


class Command(BaseCommand):
    help = "Restaure les catégories et les produits réels avec leurs images du dossier media/."

    @transaction.atomic
    def handle(self, *args, **options):
        StoreSettings.load()

        # 1. Catégories
        beauty, _ = Category.objects.get_or_create(
            slug="khaliqa-beauty",
            defaults={
                "name": "Khaliqa Beauty",
                "description": "Cosmétiques visage et lèvres : soins éclat, gloss et huiles.",
                "image": "categories/éclat_dor.jpeg",
                "position": 1,
                "is_active": True,
            }
        )
        if not beauty.image:
            beauty.image = "categories/éclat_dor.jpeg"
            beauty.save()

        hair, _ = Category.objects.get_or_create(
            slug="khaliqa-hair",
            defaults={
                "name": "Khaliqa Hair",
                "description": "Gamme capillaire complète : soins hydratants, pommades et masques réparateurs.",
                "image": "categories/Pommade_moringa.jpeg",
                "position": 2,
                "is_active": True,
            }
        )
        if not hair.image:
            hair.image = "categories/Pommade_moringa.jpeg"
            hair.save()

        self.stdout.write(self.style.SUCCESS("Catégories Khaliqa Beauty et Khaliqa Hair prêtes."))

        # 2. Définition des produits correspondant aux photos du dossier media/products/
        products_to_create = [
            {
                "category": beauty,
                "name": "Éclat d'Or",
                "sku": "KB-ECLAT-OR",
                "price": 8500,
                "compare_at_price": 10000,
                "stock": 20,
                "volume": "50 ml",
                "short_description": "Huile et soin éclat pour sublimer le teint et nourrir la peau.",
                "description": "Formule enrichie en actifs précieux pour apporter luminosité, hydratation et douceur.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/éclat_dor.jpeg",
            },
            {
                "category": beauty,
                "name": "Poussière d'Étoile",
                "sku": "KB-POUSSIERE-ETOILE",
                "price": 7500,
                "stock": 15,
                "volume": "15 ml",
                "short_description": "Gloss scintillant hydratant longue tenue effet miroir.",
                "description": "Apporte une brillance éclatante et des reflets subtils sans coller.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/poussière_détoile.jpeg",
            },
            {
                "category": beauty,
                "name": "Pure Aura",
                "sku": "KB-PURE-AURA",
                "price": 9000,
                "stock": 12,
                "volume": "30 ml",
                "short_description": "Élixir précieux pour un teint unifié et un éclat naturel.",
                "description": "Soin protecteur et régénérant convenant à tous types de peaux.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/pure_aura.jfif",
            },
            {
                "category": beauty,
                "name": "Soin Cils & Sourcils",
                "sku": "KB-SOIN-CILS",
                "price": 6000,
                "stock": 18,
                "volume": "10 ml",
                "short_description": "Huile fortifiante pousse cils et sourcils.",
                "description": "Nourrit intensément les fibres capillaires dès la racine pour des cils plus denses.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/1333cbcd-3691-460d-8f16-fa7c6d94d8f4.jfif",
            },
            {
                "category": hair,
                "name": "Pommade au Moringa",
                "sku": "KH-POMMADE-MORINGA",
                "price": 6500,
                "stock": 25,
                "volume": "150 ml",
                "short_description": "Pommade capillaire nourrissante et stimulante à l'extrait pur de Moringa.",
                "description": "Favorise la pousse saine, scelle l'hydratation et protège la fibre capillaire.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/Pommade_moringa.jpeg",
            },
            {
                "category": hair,
                "name": "Gamme Complète Aloe Vera",
                "sku": "KH-GAMME-ALOE-VERA",
                "price": 18000,
                "compare_at_price": 22000,
                "stock": 10,
                "volume": "Coffret",
                "short_description": "Rituel complet hydratant et réparateur à l'aloe vera pour cheveux secs et abîmés.",
                "description": "Shampoing doux, masque revitalisant et sérum hydratant sans rinçage.",
                "is_published": True,
                "is_featured": True,
                "image_path": "products/Gamme__aloe_verra.jfif",
            },
        ]

        for pdata in products_to_create:
            img_path = pdata.pop("image_path")
            prod, created = Product.objects.get_or_create(
                sku=pdata["sku"],
                defaults=pdata,
            )
            # Mettre à jour si déjà présent
            if not created:
                for k, v in pdata.items():
                    setattr(prod, k, v)
                prod.save()

            # Assigner l'image si elle n'existe pas déjà
            if not prod.images.filter(image=img_path).exists():
                ProductImage.objects.create(
                    product=prod,
                    image=img_path,
                    alt=prod.name,
                    position=0
                )
            self.stdout.write(f"  [OK] Produit : {prod.name} (Image: {img_path})")

        self.stdout.write(self.style.SUCCESS("\nTous les produits et images ont été configurés avec succès dans PostgreSQL !"))
