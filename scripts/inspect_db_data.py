import sqlite3
import psycopg

print("=== 1. Données dans db.sqlite3.bak (SQLite) ===")
try:
    conn_sq = sqlite3.connect("db.sqlite3.bak")
    cur_sq = conn_sq.cursor()
    cur_sq.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_sq = [r[0] for r in cur_sq.fetchall()]
    for t in sorted(tables_sq):
        cur_sq.execute(f'SELECT count(*) FROM "{t}"')
        count = cur_sq.fetchone()[0]
        if count > 0:
            print(f"  {t}: {count} ligne(s)")
    conn_sq.close()
except Exception as e:
    print(f"Erreur SQLite: {e}")

print("\n=== 2. Données dans mamy_khaliqa (PostgreSQL) ===")
try:
    with psycopg.connect("postgresql://postgres:postgres@localhost:5432/mamy_khaliqa") as conn_pg:
        with conn_pg.cursor() as cur_pg:
            cur_pg.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name;
            """)
            tables_pg = [r[0] for r in cur_pg.fetchall()]
            for t in tables_pg:
                cur_pg.execute(f'SELECT count(*) FROM "{t}"')
                count = cur_pg.fetchone()[0]
                if count > 0:
                    print(f"  {t}: {count} ligne(s)")
except Exception as e:
    print(f"Erreur mamy_khaliqa: {e}")

print("\n=== 3. Données dans khaliqa_db (Autre base PostgreSQL) ===")
try:
    with psycopg.connect("postgresql://postgres:postgres@localhost:5432/khaliqa_db") as conn_pg2:
        with conn_pg2.cursor() as cur_pg2:
            cur_pg2.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name;
            """)
            tables_pg2 = [r[0] for r in cur_pg2.fetchall()]
            for t in tables_pg2:
                cur_pg2.execute(f'SELECT count(*) FROM "{t}"')
                count = cur_pg2.fetchone()[0]
                if count > 0:
                    print(f"  {t}: {count} ligne(s)")
except Exception as e:
    print(f"Erreur khaliqa_db: {e}")
