#!/usr/bin/env python
"""
Script d'automatisation de la migration SQLite -> PostgreSQL pour Mamy Khaliqa.
"""
import os
import sys
import subprocess
from pathlib import Path
import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configuration
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
TARGET_DB = os.environ.get("POSTGRES_DB", "mamy_khaliqa")


def ensure_database():
    """Vérifie si la base de données cible existe sur PostgreSQL, sinon la crée."""
    print(f"[*] Vérification de l'existence de la base '{TARGET_DB}' sur PostgreSQL...")
    conn_params = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "dbname": "postgres",
        "autocommit": True,
    }
    try:
        with psycopg.connect(**conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
                exists = cur.fetchone()
                if not exists:
                    print(f"[+] Création de la base de données '{TARGET_DB}'...")
                    cur.execute(f'CREATE DATABASE "{TARGET_DB}" WITH ENCODING \'UTF8\';')
                    print(f"[OK] Base '{TARGET_DB}' créée avec succès.")
                else:
                    print(f"[OK] La base '{TARGET_DB}' existe déjà.")
        return True
    except Exception as e:
        print(f"[!] Erreur lors de la connexion à PostgreSQL (postgres db) : {e}")
        # Tentative de connexion directe à TARGET_DB
        try:
            conn_params["dbname"] = TARGET_DB
            with psycopg.connect(**conn_params) as conn:
                print(f"[OK] Connexion directe réussie à '{TARGET_DB}'.")
            return True
        except Exception as e2:
            print(f"[!] Échec de connexion directe à '{TARGET_DB}' : {e2}")
            return False


def run_django_command(args):
    """Exécute une commande Django manage.py."""
    cmd = [sys.executable, str(BASE_DIR / "manage.py")] + args
    print(f"[*] Exécution : {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"[!] Erreur (code {res.returncode}) :\n{res.stderr}\n{res.stdout}")
        return False, res.stdout, res.stderr
    print(res.stdout)
    return True, res.stdout, res.stderr


def reset_sequences():
    """Réinitialise les séquences d'ID pour toutes les tables Django après import de données."""
    print("[*] Réinitialisation des séquences de clés primaires dans PostgreSQL...")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    from django.core.management import call_command
    from django.apps import apps
    from django.db import connection
    from io import StringIO

    app_labels = [app.label for app in apps.get_app_configs() if app.label.startswith("apps_") or app.label in (
        "accounts", "catalog", "deliveries", "orders", "reviews", "contact",
        "store_settings", "banners", "newsletter"
    )]

    statements = []
    for label in app_labels:
        out = StringIO()
        try:
            call_command("sqlsequencereset", label, stdout=out, no_color=True)
            sql = out.getvalue().strip()
            if sql:
                statements.append(sql)
        except Exception as e:
            pass

    if statements:
        with connection.cursor() as cursor:
            for sql in statements:
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cursor.execute(stmt)
        print(f"[OK] {len(statements)} blocs de séquences réinitialisés avec succès.")
    else:
        print("[*] Aucune séquence à réinitialiser.")


def main():
    print("=" * 60)
    print("MIGRATION DES DONNÉES VERS POSTGRESQL - MAMY KHALIQA")
    print("=" * 60)

    # 1. Base PostgreSQL
    if not ensure_database():
        print("[!] Impossible de joindre PostgreSQL. Veuillez vérifier que le service est actif.")
        sys.exit(1)

    # 2. Exécution des migrations Django
    print("\n[*] Application des migrations Django sur PostgreSQL...")
    ok, out, err = run_django_command(["migrate", "--noinput"])
    if not ok:
        print("[!] Échec de l'application des migrations.")
        sys.exit(1)
    print("[OK] Migrations appliquées avec succès.")

    # 3. Chargement des données sauvegardées
    fixture = BASE_DIR / "backup_sqlite_data.json"
    if fixture.exists() and fixture.stat().st_size > 0:
        print(f"\n[*] Vérification de l'encodage UTF-8 de '{fixture.name}'...")
        raw_bytes = fixture.read_bytes()
        try:
            raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            print("[*] Conversion de l'encodage CP1252 vers UTF-8...")
            text = raw_bytes.decode("cp1252", errors="replace")
            fixture.write_text(text, encoding="utf-8")
            print("[OK] Fichier ré-encodé en UTF-8.")

        print(f"\n[*] Chargement des données depuis '{fixture.name}' ({fixture.stat().st_size} octets)...")
        ok, out, err = run_django_command(["loaddata", str(fixture)])
        if not ok:
            print("[!] Avertissement lors du chargement des données. Vérifiez les erreurs ci-dessus.")
        else:
            print("[OK] Données importées avec succès dans PostgreSQL.")
            # 4. Réinitialisation des séquences
            reset_sequences()
    else:
        print(f"[*] Fichier '{fixture.name}' absent ou vide. Aucune donnée à importer.")

    print("\n[OK] Processus de migration terminé.")


if __name__ == "__main__":
    main()
