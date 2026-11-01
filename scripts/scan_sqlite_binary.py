with open("db.sqlite3.bak", "rb") as f:
    content = f.read()

keywords = [b"Pommade", b"moringa", b"aloe", b"poussi", b"pure_aura", b"eclat", b"Gloss", b"Category", b"Product"]

for kw in keywords:
    count = content.count(kw)
    print(f"Mot-clé {kw}: {count} occurrences")
    if count > 0:
        idx = 0
        for _ in range(min(count, 3)):
            idx = content.find(kw, idx)
            start = max(0, idx - 50)
            end = min(len(content), idx + 100)
            print(f"  Snippet autour de {idx}: {content[start:end]}")
            idx += len(kw)
