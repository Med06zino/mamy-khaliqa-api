import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/postgres", autocommit=True)
cur = conn.cursor()
cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
dbs = [r[0] for r in cur.fetchall()]

for db in dbs:
    try:
        with psycopg.connect(f"postgresql://postgres:postgres@localhost:5432/{db}") as db_conn:
            with db_conn.cursor() as db_cur:
                db_cur.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name LIKE '%product%';
                """)
                tables = db_cur.fetchall()
                if tables:
                    for t in tables:
                        tname = t[0]
                        db_cur.execute(f'SELECT count(*) FROM "{tname}"')
                        cnt = db_cur.fetchone()[0]
                        if cnt > 0:
                            print(f"[FOUND] Base '{db}' -> Table '{tname}': {cnt} lignes !")
    except Exception as e:
        pass
print("Scan terminé.")
