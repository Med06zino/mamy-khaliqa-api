import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client

c = Client(SERVER_NAME="localhost")
r_cat = c.get("/api/v1/categories/")
print("CATEGORIES STATUS:", r_cat.status_code)
for cat in r_cat.json():
    print(f"  - {cat['name']} (slug: {cat['slug']}) -> Image: {cat['image']}")

r_prod = c.get("/api/v1/products/")
print("\nPRODUCTS STATUS:", r_prod.status_code)
results = r_prod.json().get("results", [])
print(f"Total produits retournés par l'API: {len(results)}")
for p in results:
    print(f"  - {p['name']} ({p['price']} FCFA) [Cat: {p['category']['name']}] -> Image: {p['main_image']}")

r_beauty = c.get("/api/v1/products/?category=khaliqa-beauty")
print(f"\nProduits Khaliqa Beauty (page d'accueil): {len(r_beauty.json().get('results', []))} produits")

r_hair = c.get("/api/v1/products/?category=khaliqa-hair")
print(f"Produits Khaliqa Hair (page d'accueil): {len(r_hair.json().get('results', []))} produits")
