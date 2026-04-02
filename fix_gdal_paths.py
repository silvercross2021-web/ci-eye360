import os

# Configuration GDAL pour Windows (via PostgreSQL 16)
POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
header = f"""import os
if os.name == "nt":
    os.environ["PATH"] = r"{POSTGRES_BIN}" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"{POSTGRES_BIN}", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"{POSTGRES_BIN}", "libgeos_c.dll")
"""

test_dir = "test_speciale"
for f in os.listdir(test_dir):
    if f.endswith(".py"):
        path = os.path.join(test_dir, f)
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()
        
        # On injecte le header seulement s'il n'est pas déjà présent
        if 'GDAL_LIBRARY_PATH' not in content:
            print(f"Correction de {f}...")
            with open(path, "w", encoding="utf-8") as file:
                file.write(header + "\n" + content)
        else:
            print(f"Déjà OK : {f}")

print("Correction terminée.")
