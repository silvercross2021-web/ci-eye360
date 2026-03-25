"""
TEST ROB — Robustesse (cas limites, valeurs nulles, NaN, tableaux vides)
"""
import os, sys, traceback
import numpy as np

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

print("\n=== TEST ROB : Robustesse et cas limites ===\n")

try:
    import django
    django.setup()
except Exception as e:
    print(f"FATAL: django.setup() failed: {e}")
    sys.exit(1)

# ROB-01 : detect_changes() avec arrays NaN
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    ndbi_t1 = np.array([[np.nan, 0.1], [0.05, 0.3]])
    ndbi_t2 = np.array([[0.4, np.nan], [0.35, 0.1]])
    result = calc.detect_changes(ndbi_t1, ndbi_t2)
    assert 'new_constructions' in result
    ok("ROB-01 : detect_changes() avec NaN — pas de crash")
except Exception as e:
    fail("ROB-01 : detect_changes() avec NaN", traceback.format_exc()[-300:])

# ROB-02 : detect_changes() dimensions incompatibles → ValueError
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    ndbi_t1 = np.zeros((10, 10))
    ndbi_t2 = np.zeros((20, 20))
    try:
        calc.detect_changes(ndbi_t1, ndbi_t2)
        fail("ROB-02 : detect_changes() dimensions incompatibles → aurait dû lever ValueError !")
    except ValueError:
        ok("ROB-02 : detect_changes() dimensions incompatibles → ValueError correcte")
    except Exception as e:
        fail("ROB-02 : Exception inattendue", str(e)[:200])
except Exception as e:
    fail("ROB-02 : test dimensions incompatibles", str(e)[:200])

# ROB-03 : extract_change_regions() masque vide
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    empty_mask = np.zeros((50, 50), dtype=bool)
    regions = calc.extract_change_regions(empty_mask)
    assert regions == [], f"Attendu [], obtenu {regions}"
    ok("ROB-03 : extract_change_regions() masque vide → [] OK")
except Exception as e:
    fail("ROB-03 : extract_change_regions() masque vide", traceback.format_exc()[-300:])

# ROB-04 : AIDetector avec tableau de zéros (edge case)
try:
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    ai = AIDetector(n_clusters=3)
    zeros = np.zeros((20, 20), dtype=np.float32)
    mask, seg = ai.predict_buildings(zeros, zeros, zeros)
    assert mask.shape == (20, 20)
    ok("ROB-04 : AIDetector avec arrays de zéros → pas de crash")
except Exception as e:
    fail("ROB-04 : AIDetector avec zéros", traceback.format_exc()[-300:])

# ROB-05 : AIDetector avec n_clusters=1 (cas limite)
try:
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    ai = AIDetector(n_clusters=1)
    b = np.random.rand(20, 20).astype(np.float32) * 3000
    mask, seg = ai.predict_buildings(b, b, b)
    ok("ROB-05 : AIDetector n_clusters=1 → pas de crash")
except Exception as e:
    fail("ROB-05 : AIDetector n_clusters=1", traceback.format_exc()[-300:])

# ROB-06 : geometry_geojson property exception safe
try:
    from module1_urbanisme.models import DetectionConstruction
    d = DetectionConstruction()
    d.geometry = None
    g = d.geometry_geojson
    assert g is None
    ok("ROB-06 : geometry_geojson(None) ne crash pas")
except Exception as e:
    fail("ROB-06 : geometry_geojson(None)", traceback.format_exc()[-300:])

# ROB-07 : DetectionConstructionSerializer avec instance sans geometry
try:
    from module1_urbanisme.serializers import DetectionConstructionSerializer
    from module1_urbanisme.models import DetectionConstruction
    d = DetectionConstruction(
        ndbi_t1=0.1, ndbi_t2=0.4, status='conforme', alert_level='vert',
        confidence=0.7
    )
    d.pk = 999  # Fake pk
    d.geometry = None
    s = DetectionConstructionSerializer(d)
    data = s.data
    # geometry_geojson doit être None (pas un crash)
    assert data.get('geometry_geojson') is None, f"geometry_geojson non None: {data.get('geometry_geojson')}"
    ok("ROB-07 : DetectionConstructionSerializer avec geometry=None → geometry_geojson=None OK")
except Exception as e:
    fail("ROB-07 : DetectionConstructionSerializer geometry=None", traceback.format_exc()[-300:])

# ROB-08 : api_detections_geojson avec detection sans geometry → ignorée
try:
    from django.test import Client
    import json
    client = Client()
    response = client.get('/api/detections-geojson/')
    if response.status_code == 200:
        data = json.loads(response.content)
        # La vue doit retourner un FeatureCollection sans crash
        assert data['type'] == 'FeatureCollection'
        ok("ROB-08 : /api/detections-geojson/ avec données (potentiellement nulles) → 200 OK")
    else:
        warn(f"ROB-08 : /api/detections-geojson/ → {response.status_code}")
except Exception as e:
    fail("ROB-08 : /api/detections-geojson/ robustesse", traceback.format_exc()[-300:])

# ROB-09 : import_google_buildings — BBOX valide (remplacement import_microsoft supprimé)
try:
    from module1_urbanisme.management.commands.import_google_buildings import TREICHVILLE_BBOX, MIN_CONFIDENCE
    minlon, minlat, maxlon, maxlat = TREICHVILLE_BBOX
    assert maxlon > minlon, f"maxLon ({maxlon}) <= minLon ({minlon})"
    assert maxlat > minlat, f"maxLat ({maxlat}) <= minLat ({minlat})"
    assert -5.0 < minlon < -3.5, f"minLon hors Abidjan: {minlon}"
    assert 5.0 < minlat < 5.5, f"minLat hors Abidjan: {minlat}"
    assert 0.6 <= MIN_CONFIDENCE <= 0.8, f"MIN_CONFIDENCE hors plage: {MIN_CONFIDENCE}"
    ok(f"ROB-09 : import_google_buildings BBOX {TREICHVILLE_BBOX} et MIN_CONFIDENCE={MIN_CONFIDENCE} valides")
except Exception as e:
    fail("ROB-09 : import_google_buildings BBOX robustesse", traceback.format_exc()[-300:])

# ROB-10 : NDBICalculator.compute_confidence() valeurs extrêmes
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    # Cloud cover 100%
    c1 = calc.compute_confidence(ndbi_t1=0.0, ndbi_t2=0.0, bsi=None, surface_px=1, cloud_cover_pct=100.0)
    assert 0.0 <= c1 <= 1.0, f"Hors bornes avec nuage 100%: {c1}"
    # Surface très grande
    c2 = calc.compute_confidence(ndbi_t1=0.5, ndbi_t2=0.9, bsi=0.5, surface_px=100000, cloud_cover_pct=0.0)
    assert 0.0 <= c2 <= 1.0, f"Hors bornes avec grande surface: {c2}"
    ok(f"ROB-10 : compute_confidence() valeurs extrêmes OK (c1={c1:.2f}, c2={c2:.2f})")
except AttributeError:
    warn("ROB-10 : compute_confidence() non disponible")
except Exception as e:
    fail("ROB-10 : compute_confidence() valeurs extrêmes", traceback.format_exc()[-300:])

# ROB-11 : HuggingFaceAIClient.batch_validate() liste vide
try:
    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
    import numpy as np
    client = HuggingFaceAIClient()
    result = client.batch_validate([], np.zeros((10, 10)), np.zeros((10, 10)))
    assert result == [], f"Attendu [], obtenu {result}"
    ok("ROB-11 : batch_validate([]) → [] OK")
except Exception as e:
    fail("ROB-11 : batch_validate([]) liste vide", traceback.format_exc()[-300:])

# ROB-12 : detect_changes() avec masque d'eau total (tout -0.3)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    # Tout de l'eau — aucune construction ne devrait être détectée
    ndbi_water = np.full((10, 10), -0.3)
    ndbi_t2_high = np.full((10, 10), 0.5)
    result = calc.detect_changes(ndbi_water, ndbi_t2_high)
    n_constr = np.sum(result['new_constructions'])
    assert n_constr == 0, f"Des constructions détectées sur l'eau : {n_constr} pixels !"
    ok("ROB-12 : Masque eau total → 0 constructions (eau correctement filtrée)")
except Exception as e:
    fail("ROB-12 : Masque eau total", traceback.format_exc()[-300:])

# ROB-13 : synthesize_b03 — import et signature
try:
    from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
    import inspect
    sig = inspect.signature(synthesize_b03)
    params = list(sig.parameters.keys())
    ok(f"ROB-13 : synthesize_b03 signature : {params}")
except Exception as e:
    fail("ROB-13 : synthesize_b03 signature", str(e)[:200])

# ROB-14 : DeepLearningDetector — chemin relatif des poids
try:
    from module1_urbanisme.pipeline.deep_learning_detector import DeepLearningDetector
    import inspect
    src = inspect.getsource(DeepLearningDetector.__init__)
    if 'settings.BASE_DIR' not in src and 'BASE_DIR' not in src:
        if 'os.path.join' in src:
            warn("ROB-14 : DeepLearningDetector utilise os.path.join sans settings.BASE_DIR",
                 "Le chemin des poids du modèle est relatif — peut crasher selon le CWD")
        else:
            warn("ROB-14 : DeepLearningDetector — chemin poids non vérifié")
    else:
        ok("ROB-14 : DeepLearningDetector utilise BASE_DIR pour les poids")
except Exception as e:
    warn("ROB-14 : DeepLearningDetector vérification", str(e)[:200])

print("\n--- RÉSUMÉ ROB ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
