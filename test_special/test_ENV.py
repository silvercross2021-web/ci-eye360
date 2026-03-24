"""
TEST ENV — Variables d'environnement et configuration Django
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

RESULTS = []

def ok(name):
    RESULTS.append(("OK", name))
    print(f"  [OK]   {name}")

def fail(name, detail=""):
    RESULTS.append(("FAIL", name, detail))
    print(f"  [FAIL] {name}")
    if detail:
        print(f"         {detail}")

def warn(name, detail=""):
    RESULTS.append(("WARN", name, detail))
    print(f"  [WARN] {name}")
    if detail:
        print(f"         {detail}")

print("\n=== TEST ENV : Variables d'environnement et configuration ===\n")

# ENV-01 : Django settings importables
try:
    import django
    django.setup()
    ok("ENV-01 : django.setup() sans erreur")
except Exception as e:
    fail("ENV-01 : django.setup()", str(e))

# ENV-02 : SECRET_KEY présente et non vide
try:
    from django.conf import settings
    assert settings.SECRET_KEY, "SECRET_KEY vide"
    ok("ENV-02 : SECRET_KEY présente")
except Exception as e:
    fail("ENV-02 : SECRET_KEY", str(e))

# ENV-03 : DEBUG configuré
try:
    from django.conf import settings
    debug_val = settings.DEBUG
    if debug_val:
        warn("ENV-03 : DEBUG=True (acceptable en dev, dangereux en prod)")
    else:
        ok("ENV-03 : DEBUG=False")
except Exception as e:
    fail("ENV-03 : DEBUG", str(e))

# ENV-04 : CORS_ALLOW_ALL_ORIGINS sécurité
try:
    from django.conf import settings
    cors = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)
    if cors and not settings.DEBUG:
        fail("ENV-04 : CORS_ALLOW_ALL_ORIGINS=True en production !")
    elif cors:
        warn("ENV-04 : CORS_ALLOW_ALL_ORIGINS=True (DEBUG=True, acceptable en dev)")
    else:
        ok("ENV-04 : CORS_ALLOW_ALL_ORIGINS=False")
except Exception as e:
    fail("ENV-04 : CORS", str(e))

# ENV-05 : GDAL/GEOS library paths
try:
    from django.conf import settings
    gdal = getattr(settings, 'GDAL_LIBRARY_PATH', None)
    geos = getattr(settings, 'GEOS_LIBRARY_PATH', None)
    if gdal and not os.path.exists(gdal):
        fail("ENV-05 : GDAL_LIBRARY_PATH pointe vers un fichier inexistant", gdal)
    elif geos and not os.path.exists(geos):
        fail("ENV-05 : GEOS_LIBRARY_PATH pointe vers un fichier inexistant", geos)
    else:
        ok("ENV-05 : GDAL/GEOS paths OK ou non définis")
except Exception as e:
    fail("ENV-05 : GDAL/GEOS paths", str(e))

# ENV-06 : INSTALLED_APPS contient les apps requises
try:
    from django.conf import settings
    required = ['django.contrib.gis', 'rest_framework', 'module1_urbanisme']
    missing = [a for a in required if a not in settings.INSTALLED_APPS]
    if missing:
        fail("ENV-06 : INSTALLED_APPS manquantes", str(missing))
    else:
        ok("ENV-06 : INSTALLED_APPS OK")
except Exception as e:
    fail("ENV-06 : INSTALLED_APPS", str(e))

# ENV-07 : TEMPLATES DIRS pointe vers le bon dossier
try:
    from django.conf import settings
    dirs = []
    for t in settings.TEMPLATES:
        dirs.extend(t.get('DIRS', []))
    dirs_str = [str(d) for d in dirs]
    templates_exist = any(os.path.isdir(d) for d in dirs_str)
    if not templates_exist and dirs_str:
        fail("ENV-07 : Aucun dossier TEMPLATES/DIRS n'existe", str(dirs_str))
    elif not dirs_str:
        warn("ENV-07 : TEMPLATES DIRS vide (APP_DIRS peut suffire)")
    else:
        ok("ENV-07 : TEMPLATES DIRS OK")
except Exception as e:
    fail("ENV-07 : TEMPLATES", str(e))

# ENV-08 : DATABASE configurée
try:
    from django.conf import settings
    db = settings.DATABASES.get('default', {})
    engine = db.get('ENGINE', '')
    if not engine:
        fail("ENV-08 : Pas de DATABASE configurée")
    elif 'postgis' in engine.lower():
        ok(f"ENV-08 : DATABASE engine = {engine}")
    elif 'sqlite' in engine.lower():
        warn(f"ENV-08 : DATABASE engine = {engine} (SQLite, PostGIS requis en prod)")
    else:
        ok(f"ENV-08 : DATABASE engine = {engine}")
except Exception as e:
    fail("ENV-08 : DATABASE", str(e))

# ENV-09 : Modules Python critiques importables
critical_imports = [
    ('numpy', 'numpy'),
    ('rasterio', 'rasterio'),
    ('sklearn', 'scikit-learn'),
    ('cv2', 'opencv-python'),
    ('scipy', 'scipy'),
    ('rest_framework', 'djangorestframework'),
]
for mod, pkg in critical_imports:
    try:
        __import__(mod)
        ok(f"ENV-09 : import {mod} OK")
    except ImportError as e:
        fail(f"ENV-09 : import {mod} (pip install {pkg})", str(e))

# ENV-10 : django.contrib.gis importable
try:
    from django.contrib.gis.geos import GEOSGeometry
    g = GEOSGeometry('{"type": "Point", "coordinates": [-4.0, 5.3]}')
    ok("ENV-10 : GeoDjango / GEOS fonctionnel")
except Exception as e:
    fail("ENV-10 : GeoDjango/GEOS", str(e))

print("\n--- RÉSUMÉ ENV ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
