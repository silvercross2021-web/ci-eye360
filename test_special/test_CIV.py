"""
TEST CIV — Contexte ivoirien (BBOX Treichville, seuils spectraux, indices)
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

print("\n=== TEST CIV : Contexte ivoirien Treichville ===\n")

try:
    import django
    django.setup()
except Exception as e:
    print(f"FATAL: django.setup() failed: {e}")
    sys.exit(1)

TREICHVILLE_BBOX = {"min_lon": -4.03001, "min_lat": 5.28501, "max_lon": -3.97301, "max_lat": 5.32053}

# CIV-01 : BBOX Treichville cohérente entre les modules
try:
    from module1_urbanisme.pipeline.sentinel_data_fetcher import TREICHVILLE_BBOX as SDF_BBOX
    from module1_urbanisme.management.commands.import_microsoft import DEFAULT_BBOX
    from module1_urbanisme.management.commands.import_google_buildings import TREICHVILLE_BBOX as GB_BBOX

    # SDF_BBOX est un dict
    sdf_lon_range = SDF_BBOX.get('max_lon', 0) - SDF_BBOX.get('min_lon', 0)
    # GB_BBOX est une liste [min_lon, min_lat, max_lon, max_lat]
    gb_lon_range = GB_BBOX[2] - GB_BBOX[0]

    if abs(sdf_lon_range - gb_lon_range) > 0.01:
        warn("CIV-01 : BBOXes Treichville légèrement différentes entre modules",
             f"SentinelDataFetcher: {SDF_BBOX}, GoogleBuildings: {GB_BBOX}")
    else:
        ok(f"CIV-01 : BBOXes Treichville cohérentes (lon range ≈ {sdf_lon_range:.4f}°)")
except Exception as e:
    fail("CIV-01 : BBOXes Treichville", traceback.format_exc()[-300:])

# CIV-02 : NDBI seuil tôle/béton ivoirien (0.2 configuré)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    assert calc.threshold_built == 0.2, f"Seuil bâti = {calc.threshold_built} (attendu 0.2)"
    assert calc.threshold_soil == 0.15, f"Seuil sol = {calc.threshold_soil} (attendu 0.15)"
    ok("CIV-02 : Seuils NDBI (0.2) et BSI (0.15) corrects pour contexte ivoirien")
except Exception as e:
    fail("CIV-02 : Seuils NDBI/BSI", str(e)[:200])

# CIV-03 : Masque eau NDBI < -0.15 (lagune Ébrié)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    # Valeurs typiques eau/lagune Ébrié (NDBI ≈ -0.3 à -0.5)
    ndbi_lagune = np.array([[-0.35, -0.28, -0.42]], dtype=float)
    ndbi_t2_constr = np.array([[0.5, 0.4, 0.3]], dtype=float)
    result = calc.detect_changes(ndbi_lagune, ndbi_t2_constr)
    n = np.sum(result['new_constructions'])
    assert n == 0, f"{n} constructions détectées sur la lagune Ébrié !"
    ok("CIV-03 : Pixels lagune Ébrié (NDBI < -0.15) correctement masqués")
except Exception as e:
    fail("CIV-03 : Masque lagune Ébrié", traceback.format_exc()[-300:])

# CIV-04 : Seuil NDBI tôle galvanisée (valeur ~0.10-0.25)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    # Tôle galvanisée ivoirienne : NDBI typiquement 0.10-0.30
    # Seuil à 0.2 → au moins les valeurs > 0.2 doivent être détectées
    ndbi_t1 = np.array([[0.05, 0.10, 0.15]], dtype=float)  # Avant construction
    ndbi_t2 = np.array([[0.25, 0.25, 0.25]], dtype=float)  # Après (tôle)
    result = calc.detect_changes(ndbi_t1, ndbi_t2)
    # Seuil = 0.2, donc T2=0.25 > 0.2 ET T1 < 0.2 → nouvelle construction
    n = np.sum(result['new_constructions'])
    assert n == 3, f"Attendu 3 détections tôle, obtenu {n}"
    ok("CIV-04 : Détection tôle ivoirienne (NDBI 0.25, seuil 0.2) → 3 pixels OK")
except Exception as e:
    fail("CIV-04 : Détection tôle ivoirienne", traceback.format_exc()[-300:])

# CIV-05 : Seuil MIN_SURFACE_M2 (200m²)
try:
    from module1_urbanisme.pipeline.verification_4_couches import MIN_SURFACE_M2
    assert MIN_SURFACE_M2 == 200, f"MIN_SURFACE_M2 = {MIN_SURFACE_M2} (attendu 200m²)"
    ok("CIV-05 : MIN_SURFACE_M2 = 200m² (petite parcelle Treichville OK)")
except ImportError:
    warn("CIV-05 : MIN_SURFACE_M2 non exporté depuis verification_4_couches")
except AssertionError as e:
    warn(f"CIV-05 : {e}")
except Exception as e:
    fail("CIV-05 : MIN_SURFACE_M2", str(e)[:200])

# CIV-06 : PIXEL_SIZE_DEGREES cohérent avec résolution Sentinel-2 à Abidjan
try:
    from module1_urbanisme.management.commands.run_detection import PIXEL_SIZE_DEGREES
    # 10m / (111000m/deg × cos(5.3°)) ≈ 0.0000904°
    expected = 10.0 / (111000 * 0.9957)  # cos(5.3°) ≈ 0.9957
    if abs(PIXEL_SIZE_DEGREES - expected) < 0.00002:
        ok(f"CIV-06 : PIXEL_SIZE_DEGREES = {PIXEL_SIZE_DEGREES:.8f} (correct à Abidjan)")
    else:
        warn(f"CIV-06 : PIXEL_SIZE_DEGREES = {PIXEL_SIZE_DEGREES:.8f}, attendu ≈ {expected:.8f}")
except Exception as e:
    fail("CIV-06 : PIXEL_SIZE_DEGREES", str(e)[:200])

# CIV-07 : _pixel_region_to_geojson produit des coordonnées dans la BBOX Treichville
try:
    from module1_urbanisme.management.commands.run_detection import Command
    import json
    from rasterio.transform import from_bounds
    cmd = Command()
    cmd.stdout = type('obj', (object,), {'write': lambda self, x: None})()

    transform = from_bounds(
        TREICHVILLE_BBOX['min_lon'], TREICHVILLE_BBOX['min_lat'],
        TREICHVILLE_BBOX['max_lon'], TREICHVILLE_BBOX['max_lat'],
        600, 400
    )
    region = {'centroid': (200, 300), 'size_pixels': 10}
    geojson_str = cmd._pixel_region_to_geojson(region, transform)
    geojson = json.loads(geojson_str)
    coords = geojson['coordinates'][0]
    for lon, lat in coords:
        assert TREICHVILLE_BBOX['min_lon'] - 0.01 < lon < TREICHVILLE_BBOX['max_lon'] + 0.01, \
            f"Longitude {lon} hors BBOX Treichville"
        assert TREICHVILLE_BBOX['min_lat'] - 0.01 < lat < TREICHVILLE_BBOX['max_lat'] + 0.01, \
            f"Latitude {lat} hors BBOX Treichville"
    ok("CIV-07 : GeoJSON généré dans BBOX Treichville (CORRECTIF A6 OK)")
except Exception as e:
    fail("CIV-07 : GeoJSON dans BBOX Treichville", traceback.format_exc()[-300:])

# CIV-08 : Vérification saison sèche Nov-Mars (Côte d'Ivoire)
try:
    from module1_urbanisme.pipeline.gee_composite import DRY_SEASON_START, DRY_SEASON_END
    # DRY_SEASON_START doit être en novembre (11)
    assert '11' in DRY_SEASON_START, f"Saison sèche start incorrecte: {DRY_SEASON_START}"
    assert '03' in DRY_SEASON_END or '3' in DRY_SEASON_END, f"Saison sèche end incorrecte: {DRY_SEASON_END}"
    ok(f"CIV-08 : Saison sèche définie : {DRY_SEASON_START} → {DRY_SEASON_END}")

    # Vérifier que ces constantes sont UTILISÉES dans le code
    import inspect
    from module1_urbanisme.pipeline import gee_composite
    src = inspect.getsource(gee_composite)
    if 'DRY_SEASON_START' not in src.replace('DRY_SEASON_START = ', ''):
        warn("CIV-08 : DRY_SEASON_START défini mais jamais utilisé dans le code !",
             "Les dates de saison sèche sont hardcodées ailleurs dans gee_composite.py")
except ImportError:
    warn("CIV-08 : DRY_SEASON_START/END non exportés de gee_composite")
except Exception as e:
    fail("CIV-08 : Saison sèche", str(e)[:200])

# CIV-09 : SAR threshold VV pour Côte d'Ivoire
try:
    from module1_urbanisme.pipeline.sentinel1_sar import THRESHOLD_VV
    if THRESHOLD_VV == 0.15:
        ok(f"CIV-09 : THRESHOLD_VV = {THRESHOLD_VV} (conforme config)")
    else:
        warn(f"CIV-09 : THRESHOLD_VV = {THRESHOLD_VV} (valeur différente de 0.15)")
except ImportError:
    warn("CIV-09 : THRESHOLD_VV non exporté de sentinel1_sar")
except Exception as e:
    fail("CIV-09 : THRESHOLD_VV", str(e)[:200])

# CIV-10 : Google Open Buildings confidence seuil
try:
    from module1_urbanisme.management.commands.import_google_buildings import MIN_CONFIDENCE
    assert 0.6 <= MIN_CONFIDENCE <= 0.75, f"MIN_CONFIDENCE hors plage: {MIN_CONFIDENCE}"
    ok(f"CIV-10 : Google Buildings MIN_CONFIDENCE = {MIN_CONFIDENCE} (plage 0.65-0.75 correcte)")
except ImportError:
    warn("CIV-10 : MIN_CONFIDENCE non exporté")
except Exception as e:
    fail("CIV-10 : MIN_CONFIDENCE", str(e)[:200])

# CIV-11 : import_sentinel_api.py - hardcoded load_dotenv() redondant
try:
    import inspect
    from module1_urbanisme.management.commands import import_sentinel_api
    src = inspect.getsource(import_sentinel_api)
    if 'load_dotenv()' in src:
        warn("CIV-11 : import_sentinel_api.py appelle load_dotenv() explicitement",
             "Dans un contexte Django (django-environ), load_dotenv() peut écraser les vars d'env gérées par django-environ")
    else:
        ok("CIV-11 : import_sentinel_api.py pas de load_dotenv() redondant")
except Exception as e:
    warn("CIV-11 : import_sentinel_api vérification", str(e)[:200])

# CIV-12 : run_detection B03 dates hardcodées vs dates réelles T1/T2
try:
    import inspect
    from module1_urbanisme.management.commands import run_detection
    src = inspect.getsource(run_detection)
    if '"2024-01-01"' in src and '"2025-01-01"' in src:
        warn("CIV-12 : run_detection.py télécharge B03 pour dates hardcodées (2024-01-01, 2025-01-01)",
             "B03 est téléchargé indépendamment des dates T1/T2 réelles passées au pipeline !")
    else:
        ok("CIV-12 : Pas de dates B03 hardcodées dans run_detection.py")
except Exception as e:
    warn("CIV-12 : Vérification dates B03", str(e)[:200])

# CIV-13 : verification_4_couches zones exclues (harbour, airport)
try:
    from module1_urbanisme.pipeline.verification_4_couches import ZONES_EXCLUES_SOIL
    assert 'harbour' in ZONES_EXCLUES_SOIL or 'port' in str(ZONES_EXCLUES_SOIL).lower(), \
        f"Zone harbour non dans ZONES_EXCLUES_SOIL: {ZONES_EXCLUES_SOIL}"
    ok(f"CIV-13 : ZONES_EXCLUES_SOIL inclut zones portuaires/aéroport : {ZONES_EXCLUES_SOIL}")
except ImportError:
    warn("CIV-13 : ZONES_EXCLUES_SOIL non exporté")
except AssertionError as e:
    warn(f"CIV-13 : {e}")
except Exception as e:
    fail("CIV-13 : ZONES_EXCLUES_SOIL", str(e)[:200])

print("\n--- RÉSUMÉ CIV ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
