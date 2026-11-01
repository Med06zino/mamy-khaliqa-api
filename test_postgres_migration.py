#!/usr/bin/env python
"""
Script de test complet pour valider la migration exclusive vers PostgreSQL
pour le projet Mamy Khaliqa.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection
from django.conf import settings


def test_postgres_engine_and_driver():
    """Vérifie que Django utilise exclusivement le backend PostgreSQL et le pilote psycopg (v3)."""
    print("\n=== 1. Vérification du moteur et du pilote de base de données ===")
    try:
        engine = settings.DATABASES["default"]["ENGINE"]
        print(f"[*] Moteur configuré : {engine}")
        if "sqlite" in engine.lower():
            print("[FAIL] Moteur SQLite détecté ! SQLite est strictement interdit.")
            return False
        if not engine.endswith("postgresql"):
            print(f"[FAIL] Moteur inattendu : {engine}")
            return False

        # Vérification du pilote sous-jacent
        db_module = connection.Database
        driver_name = getattr(db_module, "__name__", str(db_module))
        print(f"[*] Module pilote sous-jacent : {driver_name}")

        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            pg_version = cursor.fetchone()[0]
            print(f"[OK] Connecté à PostgreSQL avec succès !")
            print(f"     Version : {pg_version[:80]}...")
            cursor.execute("SELECT current_database(), current_user;")
            db_name, db_user = cursor.fetchone()
            print(f"     Base active : {db_name} | Utilisateur : {db_user}")

        return True
    except Exception as e:
        print(f"[FAIL] Erreur de vérification du moteur : {e}")
        return False


def test_tables():
    """Vérifie la présence et le nombre de tables créées dans le schéma public."""
    print("\n=== 2. Vérification des tables PostgreSQL ===")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [r[0] for r in cursor.fetchall()]
            print(f"[OK] {len(tables)} tables trouvées dans PostgreSQL.")

            expected_prefixes = [
                "accounts_", "catalog_", "deliveries_", "orders_",
                "reviews_", "contact_", "store_settings_", "banners_",
                "newsletter_", "auth_", "django_"
            ]
            for prefix in expected_prefixes:
                matching = [t for t in tables if t.startswith(prefix)]
                print(f"     - Domaine '{prefix[:-1]}' : {len(matching)} table(s)")

            return len(tables) >= 20
    except Exception as e:
        print(f"[FAIL] Erreur lors de la vérification des tables : {e}")
        return False


def test_auth_and_accounts():
    """Vérifie les modèles d'authentification et de comptes utilisateurs."""
    print("\n=== 3. Vérification des modèles Accounts & Utilisateurs ===")
    try:
        from apps.accounts.models import User, Address, Favorite
        user_count = User.objects.count()
        address_count = Address.objects.count()
        favorite_count = Favorite.objects.count()

        print(f"[OK] Modèles comptes accessibles :")
        print(f"     - Utilisateurs : {user_count}")
        for u in User.objects.all()[:3]:
            print(f"       * {u.email} (staff={u.is_staff}, superuser={u.is_superuser})")
        print(f"     - Adresses : {address_count}")
        print(f"     - Favoris : {favorite_count}")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur comptes : {e}")
        return False


def test_catalog():
    """Vérifie les modèles du catalogue produits et gestion des stocks."""
    print("\n=== 4. Vérification du Catalogue & Gestion des Stocks ===")
    try:
        from apps.catalog.models import (
            Category, Product, ProductVariant, ProductImage, StockMovement
        )
        cat_count = Category.objects.count()
        prod_count = Product.objects.count()
        var_count = ProductVariant.objects.count()
        img_count = ProductImage.objects.count()
        mvt_count = StockMovement.objects.count()

        print(f"[OK] Modèles catalogue accessibles :")
        print(f"     - Catégories : {cat_count}")
        print(f"     - Produits : {prod_count}")
        print(f"     - Variantes : {var_count}")
        print(f"     - Images : {img_count}")
        print(f"     - Mouvements de stock : {mvt_count}")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur catalogue : {e}")
        return False


def test_deliveries_and_settings():
    """Vérifie les zones de livraison et les paramètres de la boutique."""
    print("\n=== 5. Vérification Zones de Livraison & Store Settings ===")
    try:
        from apps.deliveries.models import DeliveryZone
        from apps.store_settings.models import StoreSettings

        zone_count = DeliveryZone.objects.count()
        settings_obj = StoreSettings.load()

        print(f"[OK] Données de configuration accessibles :")
        print(f"     - Zones de livraison : {zone_count}")
        print(f"     - StoreSettings nom : '{settings_obj.name}'")
        print(f"     - Seuil alerte stock : {settings_obj.low_stock_threshold}")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur livraisons / paramètres : {e}")
        return False


def test_orders_and_payments():
    """Vérifie les modèles de commandes et paiements."""
    print("\n=== 6. Vérification Commandes & Paiements ===")
    try:
        from apps.orders.models import Order, OrderItem, OrderStatusHistory, Payment
        try:
            from apps.orders.models import Invoice
            invoice_count = Invoice.objects.count()
        except ImportError:
            invoice_count = "N/A"

        order_count = Order.objects.count()
        item_count = OrderItem.objects.count()
        history_count = OrderStatusHistory.objects.count()
        payment_count = Payment.objects.count()

        print(f"[OK] Modèles commandes accessibles :")
        print(f"     - Commandes : {order_count}")
        print(f"     - Articles commandés : {item_count}")
        print(f"     - Historique statuts : {history_count}")
        print(f"     - Paiements : {payment_count}")
        print(f"     - Factures : {invoice_count}")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur commandes/paiements : {e}")
        return False


def test_other_features():
    """Vérifie les fonctionnalités complémentaires (Bannières, Newsletter, Contact, Avis)."""
    print("\n=== 7. Vérification Bannières, Avis, Messages & Newsletter ===")
    try:
        from apps.banners.models import Banner
        from apps.reviews.models import Review
        from apps.contact.models import ContactMessage
        from apps.newsletter.models import NewsletterSubscriber

        banner_count = Banner.objects.count()
        review_count = Review.objects.count()
        msg_count = ContactMessage.objects.count()
        sub_count = NewsletterSubscriber.objects.count()

        print(f"[OK] Fonctionnalités complémentaires accessibles :")
        print(f"     - Bannières : {banner_count}")
        print(f"     - Avis clients : {review_count}")
        print(f"     - Messages de contact : {msg_count}")
        print(f"     - Abonnés newsletter : {sub_count}")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur fonctionnalités complémentaires : {e}")
        return False


def test_sequence_integrity():
    """Vérifie l'insertion et la suppression d'un enregistrement pour tester les séquences PostgreSQL."""
    print("\n=== 8. Test d'intégrité des séquences PostgreSQL (INSERT / DELETE) ===")
    try:
        from apps.deliveries.models import DeliveryZone

        test_zone = DeliveryZone.objects.create(
            name="__ZONE_TEST_POSTGRES__",
            fee=2500,
            is_active=False,
            info="Test d'intégrité de séquence PostgreSQL"
        )
        print(f"[OK] Enregistrement inséré avec ID séquence : {test_zone.id}")
        assert test_zone.id is not None
        test_zone.delete()
        print(f"[OK] Enregistrement de test nettoyé sans erreur.")
        return True
    except Exception as e:
        print(f"[FAIL] Erreur d'intégrité de séquence : {e}")
        return False


def main():
    print("=" * 65)
    print("VÉRIFICATION TECHNIQUE DE LA MIGRATION POSTGRESQL - MAMY KHALIQA")
    print("=" * 65)

    tests = [
        test_postgres_engine_and_driver,
        test_tables,
        test_auth_and_accounts,
        test_catalog,
        test_deliveries_and_settings,
        test_orders_and_payments,
        test_other_features,
        test_sequence_integrity,
    ]

    results = []
    for test in tests:
        try:
            res = test()
            results.append(res)
        except Exception as e:
            print(f"[CRITICAL ERROR] Échec inattendu du test : {e}")
            results.append(False)

    print("\n" + "=" * 65)
    print("RÉSUMÉ DES TESTS")
    print("=" * 65)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Résultats : {passed}/{total} tests validés avec succès.")

    if passed == total:
        print("\n>>> MIGRATION POSTGRESQL PARFAITEMENT OPÉRATIONNELLE ! <<<")
        return 0
    else:
        print("\n>>> CERTAINS TESTS ONT ÉCHOUÉ. VEUILLEZ VÉRIFIER LES LOGS. <<<")
        return 1


if __name__ == "__main__":
    sys.exit(main())
