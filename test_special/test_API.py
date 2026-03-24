"""
TEST API — Endpoints REST DRF (serializers, viewsets, URL routing)
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

print("\n=== TEST API : Endpoints REST ===\n")

try:
    import django
    django.setup()
except Exception as e:
    print(f"FATAL: django.setup() failed: {e}")
    sys.exit(1)

# API-01 : Tous les serializers importables sans erreur
try:
    from module1_urbanisme.serializers import (
        ZoneCadastraleSerializer, ImageSatelliteSerializer,
        MicrosoftFootprintSerializer, DetectionConstructionSerializer,
        DetectionCreateSerializer, DetectionUpdateSerializer, StatisticsSerializer
    )
    ok("API-01 : Tous les serializers importables")
except Exception as e:
    fail("API-01 : Import serializers", traceback.format_exc()[-300:])

# API-02 : Serializers simples importables
try:
    from module1_urbanisme.serializers_simple import (
        ZoneCadastraleSimpleSerializer, DetectionConstructionSimpleSerializer
    )
    ok("API-02 : Serializers simples importables")
except Exception as e:
    fail("API-02 : Import serializers_simple", traceback.format_exc()[-300:])

# API-03 : DetectionConstructionSerializer.fields inclut geometry_geojson
try:
    from module1_urbanisme.serializers import DetectionConstructionSerializer
    s = DetectionConstructionSerializer()
    fields = list(s.fields.keys())
    if 'geometry_geojson' in fields:
        ok("API-03 : geometry_geojson présent dans DetectionConstructionSerializer")
    else:
        warn("API-03 : geometry_geojson absent de DetectionConstructionSerializer")
except Exception as e:
    fail("API-03 : DetectionConstructionSerializer fields", traceback.format_exc()[-300:])

# API-04 : DetectionConstructionSimpleSerializer.fields inclut geometry_geojson
try:
    from module1_urbanisme.serializers_simple import DetectionConstructionSimpleSerializer
    s = DetectionConstructionSimpleSerializer()
    fields = list(s.fields.keys())
    if 'geometry_geojson' in fields:
        ok("API-04 : geometry_geojson présent dans DetectionConstructionSimpleSerializer")
    else:
        warn("API-04 : geometry_geojson absent de DetectionConstructionSimpleSerializer")
except Exception as e:
    fail("API-04 : DetectionConstructionSimpleSerializer fields", traceback.format_exc()[-300:])

# API-05 : Django test client — /api/v1/ accessible
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/')
    if response.status_code in [200, 301, 302]:
        ok(f"API-05 : GET /api/v1/ → {response.status_code}")
    else:
        warn(f"API-05 : GET /api/v1/ → {response.status_code} (inattendu)")
except Exception as e:
    fail("API-05 : GET /api/v1/", str(e)[:200])

# API-06 : /api/v1/zones-cadastrales/ accessible
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/zones-cadastrales/')
    if response.status_code == 200:
        ok(f"API-06 : GET /api/v1/zones-cadastrales/ → 200")
    else:
        fail(f"API-06 : GET /api/v1/zones-cadastrales/ → {response.status_code}")
except Exception as e:
    fail("API-06 : GET /api/v1/zones-cadastrales/", str(e)[:200])

# API-07 : /api/v1/detections/ accessible
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/detections/')
    if response.status_code == 200:
        ok(f"API-07 : GET /api/v1/detections/ → 200")
    else:
        fail(f"API-07 : GET /api/v1/detections/ → {response.status_code}")
except Exception as e:
    fail("API-07 : GET /api/v1/detections/", str(e)[:200])

# API-08 : /api/v1/detections/statistics/ accessible
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/detections/statistics/')
    if response.status_code == 200:
        ok(f"API-08 : GET /api/v1/detections/statistics/ → 200")
    else:
        fail(f"API-08 : GET /api/v1/detections/statistics/ → {response.status_code}")
except Exception as e:
    fail("API-08 : GET /api/v1/detections/statistics/", str(e)[:200])

# API-09 : /api/v1/dashboard/resume/ accessible
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/dashboard/resume/')
    if response.status_code == 200:
        ok(f"API-09 : GET /api/v1/dashboard/resume/ → 200")
    else:
        fail(f"API-09 : GET /api/v1/dashboard/resume/ → {response.status_code}")
except Exception as e:
    fail("API-09 : GET /api/v1/dashboard/resume/", str(e)[:200])

# API-10 : /api/v2/detections-simple/ (API simplifiée)
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v2/detections-simple/')
    if response.status_code == 200:
        ok(f"API-10 : GET /api/v2/detections-simple/ → 200")
    else:
        fail(f"API-10 : GET /api/v2/detections-simple/ → {response.status_code}")
except Exception as e:
    fail("API-10 : GET /api/v2/detections-simple/", str(e)[:200])

# API-11 : DetectionUpdateSerializer exige commentaire pour 'confirme'
try:
    from module1_urbanisme.serializers import DetectionUpdateSerializer
    # Sans commentaire : doit échouer
    s = DetectionUpdateSerializer(data={'statut_traitement': 'confirme', 'commentaire_terrain': ''})
    is_valid = s.is_valid()
    if not is_valid:
        ok("API-11 : DetectionUpdateSerializer refuse 'confirme' sans commentaire")
    else:
        fail("API-11 : DetectionUpdateSerializer accepte 'confirme' sans commentaire (validation manquante)")
except Exception as e:
    fail("API-11 : DetectionUpdateSerializer validation", traceback.format_exc()[-300:])

# API-12 : ordering par 'priority_score' — comportement
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/v1/detections/?ordering=priority_score')
    if response.status_code == 200:
        warn("API-12 : ?ordering=priority_score retourne 200 (tri silencieusement ignoré ou ORM crash différé)")
    elif response.status_code == 500:
        fail("API-12 : ?ordering=priority_score cause une erreur 500 serveur !")
    else:
        ok(f"API-12 : ?ordering=priority_score → {response.status_code}")
except Exception as e:
    fail("API-12 : ordering priority_score", str(e)[:200])

# API-13 : POST /api/v1/detections/ sans authentification
try:
    from django.test import Client
    client = Client()
    response = client.post('/api/v1/detections/', data={
        'ndbi_t1': 0.1, 'ndbi_t2': 0.4,
        'status': 'conforme', 'alert_level': 'vert',
        'geometry_geojson': '{"type":"Polygon","coordinates":[[[-4.01,5.30],[-4.009,5.30],[-4.009,5.301],[-4.01,5.301],[-4.01,5.30]]]}'
    }, content_type='application/json')
    if response.status_code in [200, 201]:
        # Vérifier si geometry est null dans la réponse
        import json
        try:
            data = json.loads(response.content)
            if data.get('geometry_geojson') is None:
                warn("API-13 : POST crée une détection mais geometry=NULL (geometry_geojson est read-only !)")
            else:
                ok(f"API-13 : POST /api/v1/detections/ → {response.status_code} avec géométrie")
        except Exception:
            ok(f"API-13 : POST /api/v1/detections/ → {response.status_code}")
    elif response.status_code == 400:
        ok(f"API-13 : POST /api/v1/detections/ → 400 (validation correcte)")
    else:
        warn(f"API-13 : POST /api/v1/detections/ → {response.status_code}")
except Exception as e:
    fail("API-13 : POST /api/v1/detections/", str(e)[:200])

# API-14 : /api/statistics/ (endpoint web)
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/statistics/')
    if response.status_code == 200:
        ok("API-14 : GET /api/statistics/ (web) → 200")
    else:
        warn(f"API-14 : GET /api/statistics/ → {response.status_code}")
except Exception as e:
    fail("API-14 : GET /api/statistics/", str(e)[:200])

# API-15 : /api/detections-geojson/ (endpoint web)
try:
    from django.test import Client
    client = Client()
    response = client.get('/api/detections-geojson/')
    if response.status_code == 200:
        ok("API-15 : GET /api/detections-geojson/ → 200")
    else:
        warn(f"API-15 : GET /api/detections-geojson/ → {response.status_code}")
except Exception as e:
    fail("API-15 : GET /api/detections-geojson/", str(e)[:200])

print("\n--- RÉSUMÉ API ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
