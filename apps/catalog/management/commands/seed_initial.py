from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product
from apps.store_settings.models import StoreSettings

CATEGORIES = [
    ("Huile pousse-cils", "Soins dédiés aux cils."),
    ("Gamme capillaire", "Soins pour les cheveux."),
    ("Gloss", "Gloss pour les lèvres."),
]


class Command(BaseCommand):
    help = "Cree les 3 categories initiales et les parametres. N'ecrase jamais les donnees existantes."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Ajoute 3 produits de demonstration (developpement uniquement).")

    def handle(self, *args, **opts):
        StoreSettings.load()
        for i, (name, desc) in enumerate(CATEGORIES):
            _, created = Category.objects.get_or_create(name=name, defaults={"description": desc, "position": i})
            self.stdout.write(f"{'Creee' if created else 'Existe deja'} : {name}")
        if opts["demo"]:
            for i, cat in enumerate(Category.objects.all()):
                Product.objects.get_or_create(
                    sku=f"DEMO-{i + 1}",
                    defaults={"category": cat, "name": f"Produit de demonstration {i + 1}", "price": 5000 + i * 1000,
                              "stock": 10, "is_published": True},
                )
            self.stdout.write("Produits de demonstration ajoutes (a supprimer avant le lancement).")
