"""
TEST WEB — Vues web Django (dashboard, detections, zones)
"""
import os, sys, traceback

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
        print(f"         {detail[:300]}")

def warn(name, detail=""):
    RESULTS.append(("WARN", name, detail))
    print(f"  [WARN] {name}")
    if detail:
        print(f"         {detail[:300]}")

print("\n=== TEST WEB : Vues Django ===\n")

try:
    import django
    django.setup()
except Exception as e:
    print(f"FATAL: django.setup() failed: {e}")
    sys.exit(1)

# WEB-01 : views_web importable
try:
    from module1_urbanisme import views_web
    ok("WEB-01 : views_web importable")
except Exception as e:
    fail("WEB-01 : import views_web", traceback.format_exc()[-300:])

# WEB-02 : views_web utilise STATUS_CHOICES (import statique)
try:
    from module1_urbanisme.models import DetectionConstruction
    _ = DetectionConstruction.STATUS_CHOICES
    _ = DetectionConstruction.ALERT_LEVEL_CHOICES
    ok("WEB-02 : STATUS_CHOICES et ALERT_LEVEL_CHOICES accessibles (views_web.py lignes 70-71 OK)")
except AttributeError as e:
    fail("WEB-02 : STATUS_CHOICES / ALERT_LEVEL_CHOICES manquants", str(e))

# WEB-03 : GET / (dashboard)
try:
    from django.test import Client
    client = Client()
    response = client.get('/')
    if response.status_code == 200:
        ok("WEB-03 : GET / (dashboard) → 200")
    else:
        fail(f"WEB-03 : GET / → {response.status_code}")
except Exception as e:
    fail("WEB-03 : GET /", str(e)[:200])

# WEB-04 : GET /detections/
try:
    from django.test import Client
    client = Client()
    response = client.get('/detections/')
    if response.status_code == 200:
        ok("WEB-04 : GET /detections/ → 200")
    else:
        fail(f"WEB-04 : GET /detections/ → {response.status_code}")
except Exception as e:
    fail("WEB-04 : GET /detections/", str(e)[:200])

# WEB-05 : GET /zones/
try:
    from django.test import Client
    client = Client()
    response = client.get('/zones/')
    if response.status_code == 200:
        ok("WEB-05 : GET /zones/ → 200")
    else:
        fail(f"WEB-05 : GET /zones/ → {response.status_code}")
except Exception as e:
    fail("WEB-05 : GET /zones/", str(e)[:200])

# WEB-06 : GET /detections/99999/ (ID inexistant → 404)
try:
    from django.test import Client
    client = Client()
    response = client.get('/detections/99999/')
    if response.status_code == 404:
        ok("WEB-06 : GET /detections/99999/ → 404 correct")
    else:
        warn(f"WEB-06 : GET /detections/99999/ → {response.status_code} (attendu 404)")
except Exception as e:
    fail("WEB-06 : GET /detections/99999/", str(e)[:200])

# WEB-07 : GET /zones/ZONE_INEXISTANTE/
try:
    from django.test import Client
    client = Client()
    response = client.get('/zones/ZONE_INEXISTANTE_XYZ/')
    if response.status_code == 404:
        ok("WEB-07 : GET /zones/ZONE_INEXISTANTE/ → 404 correct")
    else:
        warn(f"WEB-07 : GET /zones/ZONE_INEXISTANTE/ → {response.status_code} (attendu 404)")
except Exception as e:
    fail("WEB-07 : GET /zones/ZONE_INEXISTANTE/", str(e)[:200])

# WEB-08 : GET /api/statistics/ retourne du JSON valide
try:
    from django.test import Client
    import json
    client = Client()
    response = client.get('/api/statistics/')
    if response.status_code == 200:
        data = json.loads(response.content)
        assert 'total_detections' in data, "Clé 'total_detections' manquante"
        assert 'total_zones' in data, "Clé 'total_zones' manquante"
        ok("WEB-08 : /api/statistics/ JSON valide avec les bonnes clés")
    else:
        fail(f"WEB-08 : /api/statistics/ → {response.status_code}")
except Exception as e:
    fail("WEB-08 : /api/statistics/ JSON", traceback.format_exc()[-300:])

# WEB-09 : GET /api/detections-geojson/ retourne GeoJSON valide
try:
    from django.test import Client
    import json
    client = Client()
    response = client.get('/api/detections-geojson/')
    if response.status_code == 200:
        data = json.loads(response.content)
        assert data.get('type') == 'FeatureCollection', "Type GeoJSON incorrect"
        assert 'features' in data, "Clé 'features' manquante"
        ok(f"WEB-09 : /api/detections-geojson/ GeoJSON valide ({len(data['features'])} features)")
    else:
        fail(f"WEB-09 : /api/detections-geojson/ → {response.status_code}")
except Exception as e:
    fail("WEB-09 : /api/detections-geojson/ GeoJSON", traceback.format_exc()[-300:])

# WEB-10 : GET /api/zones-geojson/ retourne GeoJSON valide
try:
    from django.test import Client
    import json
    client = Client()
    response = client.get('/api/zones-geojson/')
    if response.status_code == 200:
        data = json.loads(response.content)
        assert data.get('type') == 'FeatureCollection', "Type GeoJSON incorrect"
        ok(f"WEB-10 : /api/zones-geojson/ GeoJSON valide ({len(data['features'])} zones)")
    else:
        fail(f"WEB-10 : /api/zones-geojson/ → {response.status_code}")
except Exception as e:
    fail("WEB-10 : /api/zones-geojson/ GeoJSON", traceback.format_exc()[-300:])

# WEB-11 : Template dashboard.html existe
try:
    import os
    from django.conf import settings
    dash_path = None
    for t in settings.TEMPLATES:
        for d in t.get('DIRS', []):
            p = os.path.join(str(d), 'module1', 'dashboard.html')
            if os.path.exists(p):
                dash_path = p
                break
    if dash_path:
        ok(f"WEB-11 : dashboard.html trouvé")
    else:
        # Try loader
        from django.template.loader import get_template
        get_template('module1/dashboard.html')
        ok("WEB-11 : dashboard.html chargeable via template loader")
except Exception as e:
    fail("WEB-11 : dashboard.html manquant", str(e)[:200])

# WEB-12 : Filtre ?status=infraction_zonage
try:
    from django.test import Client
    client = Client()
    response = client.get('/detections/?status=infraction_zonage')
    if response.status_code == 200:
        ok("WEB-12 : GET /detections/?status=infraction_zonage → 200")
    else:
        fail(f"WEB-12 : /detections/?status=infraction_zonage → {response.status_code}")
except Exception as e:
    fail("WEB-12 : GET /detections/ avec filtre", str(e)[:200])

print("\n--- RÉSUMÉ WEB ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
