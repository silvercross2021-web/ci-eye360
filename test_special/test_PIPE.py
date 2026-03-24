"""
TEST PIPE — Pipeline de détection (NDBI, BSI, AIDetector, NDBICalculator)
Tests purement numériques, sans base de données ni fichiers raster.
"""
import os, sys
import traceback
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
        print(f"         {detail[:200]}")

def warn(name, detail=""):
    RESULTS.append(("WARN", name, detail))
    print(f"  [WARN] {name}")
    if detail:
        print(f"         {detail[:200]}")

print("\n=== TEST PIPE : Pipeline de détection (numérique) ===\n")

# PIPE-01 : NDBICalculator importable
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    ok("PIPE-01 : NDBICalculator importable")
except Exception as e:
    fail("PIPE-01 : NDBICalculator import", str(e))

# PIPE-02 : detect_changes() avec arrays numpy directs
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    ndbi_t1 = np.array([[0.1, 0.05, -0.2], [0.1, 0.08, 0.3]], dtype=float)
    ndbi_t2 = np.array([[0.35, 0.05, -0.2], [0.1, 0.08, 0.3]], dtype=float)
    result = calc.detect_changes(ndbi_t1, ndbi_t2)
    assert 'new_constructions' in result, "Clé 'new_constructions' manquante"
    assert 'soil_activity' in result, "Clé 'soil_activity' manquante"
    assert 'demolished' in result, "Clé 'demolished' manquante"
    assert 'all_changes' in result, "Clé 'all_changes' manquante"
    # [0,0] : NDBI passe de 0.1 → 0.35 : nouvelle construction
    assert result['new_constructions'][0, 0] == True, "Pixel [0,0] devrait être nouvelle construction"
    ok("PIPE-02 : detect_changes() OK, logique construction correcte")
except Exception as e:
    fail("PIPE-02 : detect_changes()", traceback.format_exc()[-300:])

# PIPE-03 : BSI = NDBI (formule identique — bug scientifique documenté)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    import tempfile, rasterio
    from rasterio.transform import from_bounds
    calc = NDBICalculator()
    arr_b08 = np.random.rand(10, 10).astype(np.float32) * 0.5 + 0.1
    arr_b11 = np.random.rand(10, 10).astype(np.float32) * 0.5 + 0.1
    with tempfile.TemporaryDirectory() as tmpdir:
        b08_path = os.path.join(tmpdir, "B08.tif")
        b11_path = os.path.join(tmpdir, "B11.tif")
        b04_path = os.path.join(tmpdir, "B04.tif")
        profile = {'driver': 'GTiff', 'height': 10, 'width': 10, 'count': 1,
                   'dtype': 'float32', 'crs': 'EPSG:4326',
                   'transform': from_bounds(-4.03, 5.28, -3.97, 5.32, 10, 10)}
        with rasterio.open(b08_path, 'w', **profile) as dst: dst.write(arr_b08, 1)
        with rasterio.open(b11_path, 'w', **profile) as dst: dst.write(arr_b11, 1)
        with rasterio.open(b04_path, 'w', **profile) as dst: dst.write(arr_b08, 1)  # B04 dummy
        ndbi_arr = calc.calculate_ndbi(b08_path, b11_path)
        bsi_arr  = calc.calculate_bsi(b04_path, b08_path, b11_path)
        are_identical = np.allclose(ndbi_arr, bsi_arr, atol=1e-6)
        if are_identical:
            warn("PIPE-03 : BSI == NDBI (formule identique : B04 ignoré — bug scientifique)",
                 "calculate_bsi() utilise (B11-B08)/(B11+B08) = NDBI. B04 passé mais jamais utilisé.")
        else:
            ok("PIPE-03 : BSI ≠ NDBI (formules distinctes)")
except Exception as e:
    fail("PIPE-03 : BSI vs NDBI", traceback.format_exc()[-300:])

# PIPE-04 : AIDetector importable et prédiction sur arrays numpy
try:
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    ai = AIDetector(n_clusters=3)
    b04 = np.random.rand(20, 20).astype(np.float32) * 3000
    b08 = np.random.rand(20, 20).astype(np.float32) * 3000
    b11 = np.random.rand(20, 20).astype(np.float32) * 3000
    mask, segmented = ai.predict_buildings(b04, b08, b11)
    assert mask.shape == (20, 20), f"Shape masque inattendue: {mask.shape}"
    assert set(np.unique(mask)).issubset({0, 1}), f"Valeurs masque hors [0,1]: {np.unique(mask)}"
    ok("PIPE-04 : AIDetector.predict_buildings() OK")
except Exception as e:
    fail("PIPE-04 : AIDetector.predict_buildings()", traceback.format_exc()[-300:])

# PIPE-05 : AIDetector.compute_features() avec dict de bandes
try:
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    ai = AIDetector(n_clusters=3)
    bands = {
        'B04': np.random.rand(20, 20).astype(np.float32) * 3000,
        'B08': np.random.rand(20, 20).astype(np.float32) * 3000,
        'B11': np.random.rand(20, 20).astype(np.float32) * 3000,
    }
    feats = ai.compute_features(bands['B04'], bands['B08'], bands['B11'])
    assert feats is not None, "compute_features() a retourné None"
    ok("PIPE-05 : AIDetector.compute_features() OK")
except AttributeError as e:
    # Si compute_features accepte un dict (nouvelle API refactorisée)
    try:
        from module1_urbanisme.pipeline.ai_detector import AIDetector
        ai = AIDetector(n_clusters=3)
        bands = {
            'B04': np.random.rand(20, 20).astype(np.float32) * 3000,
            'B08': np.random.rand(20, 20).astype(np.float32) * 3000,
            'B11': np.random.rand(20, 20).astype(np.float32) * 3000,
        }
        feats = ai.compute_features(bands)
        assert feats is not None
        ok("PIPE-05 : AIDetector.compute_features(dict) OK (nouvelle API)")
    except Exception as e2:
        fail("PIPE-05 : AIDetector.compute_features()", str(e2)[:200])
except Exception as e:
    fail("PIPE-05 : AIDetector.compute_features()", traceback.format_exc()[-300:])

# PIPE-06 : extract_change_regions() avec masque numpy
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:15, 10:15] = True  # carré 5x5 = 25 pixels
    mask[30:33, 30:33] = True  # carré 3x3 = 9 pixels
    regions = calc.extract_change_regions(mask, min_size=2)
    assert len(regions) == 2, f"Attendu 2 régions, obtenu {len(regions)}"
    sizes = sorted([r['size_pixels'] for r in regions])
    assert sizes == [9, 25], f"Tailles attendues [9, 25], obtenu {sizes}"
    ok("PIPE-06 : extract_change_regions() OK, 2 régions correctes")
except Exception as e:
    fail("PIPE-06 : extract_change_regions()", traceback.format_exc()[-300:])

# PIPE-07 : extract_change_regions() — filtre taille minimale
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    mask = np.zeros((50, 50), dtype=bool)
    mask[5, 5] = True  # 1 pixel — trop petit
    mask[10:15, 10:15] = True  # 25 pixels — OK
    regions = calc.extract_change_regions(mask, min_size=2)
    assert len(regions) == 1, f"Attendu 1 région (1px filtré), obtenu {len(regions)}"
    ok("PIPE-07 : extract_change_regions() filtre min_size OK")
except Exception as e:
    fail("PIPE-07 : extract_change_regions() filtre", traceback.format_exc()[-300:])

# PIPE-08 : NDBICalculator.compute_confidence()
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    conf = calc.compute_confidence(
        ndbi_t1=0.05, ndbi_t2=0.45, bsi=0.3, surface_px=50, cloud_cover_pct=5.0
    )
    assert 0.0 <= conf <= 1.0, f"Confiance hors [0,1]: {conf}"
    ok(f"PIPE-08 : compute_confidence() OK → {conf:.3f}")
except AttributeError:
    warn("PIPE-08 : compute_confidence() non disponible (méthode absente ?)")
except Exception as e:
    fail("PIPE-08 : compute_confidence()", str(e)[:200])

# PIPE-09 : Masque eau dans detect_changes (NDBI < -0.15)
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    ndbi_t1 = np.array([[-0.3, 0.1]], dtype=float)  # -0.3 = eau
    ndbi_t2 = np.array([[0.5, 0.35]], dtype=float)   # les deux dépassent le seuil
    result = calc.detect_changes(ndbi_t1, ndbi_t2)
    # Le pixel eau [0,0] ne doit PAS être en nouvelle construction
    assert result['new_constructions'][0, 0] == False, "Pixel eau détecté comme construction !"
    assert result['new_constructions'][0, 1] == True, "Pixel bâti manqué"
    ok("PIPE-09 : Masque eau dans detect_changes() OK")
except Exception as e:
    fail("PIPE-09 : Masque eau", traceback.format_exc()[-300:])

# PIPE-10 : b03_synthesizer importable et fonctionnel
try:
    from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
    ok("PIPE-10 : b03_synthesizer.synthesize_b03 importable")
except Exception as e:
    fail("PIPE-10 : b03_synthesizer", str(e)[:200])

# PIPE-11 : HuggingFaceAIClient local scoring
try:
    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
    client = HuggingFaceAIClient()
    ndbi_t1_arr = np.full((20, 20), 0.1)
    ndbi_t2_arr = np.full((20, 20), 0.45)
    region = {
        'change_type': 'new_construction', 'centroid': (10, 10),
        'bbox': (8, 8, 12, 12), 'size_pixels': 16, 'confidence': 0.5,
        'ndbi_t1': 0.1, 'ndbi_t2': 0.45, 'bsi': 0.25,
        'geometry_geojson': '{"type":"Polygon","coordinates":[[[-4.01,5.30],[-4.009,5.30],[-4.009,5.301],[-4.01,5.301],[-4.01,5.30]]]}'
    }
    validated = client.batch_validate([region], ndbi_t1_arr, ndbi_t2_arr)
    assert len(validated) == 1, "batch_validate() doit retourner 1 région"
    assert 'confidence' in validated[0], "Pas de clé 'confidence' dans la région validée"
    ok(f"PIPE-11 : HuggingFaceAIClient.batch_validate() OK → conf={validated[0]['confidence']:.3f}")
except Exception as e:
    fail("PIPE-11 : HuggingFaceAIClient", traceback.format_exc()[-300:])

print("\n--- RÉSUMÉ PIPE ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
