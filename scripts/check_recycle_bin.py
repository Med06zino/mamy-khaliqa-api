import os

rb_path = r"C:\$Recycle.Bin"
try:
    for root, dirs, files in os.walk(rb_path):
        for f in files:
            lower = f.lower()
            if any(k in lower for k in ["sqlite", "json", "khaliqa", "mamy"]):
                full = os.path.join(root, f)
                size = os.path.getsize(full)
                print(f"[RECYCLE BIN] {full} ({size} bytes)")
except Exception as e:
    print(f"Erreur Recycle Bin: {e}")
