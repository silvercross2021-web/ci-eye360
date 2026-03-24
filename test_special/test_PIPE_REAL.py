"""
TEST PIPE RÉEL — Pipeline sur vraies données Sentinel-2 (TIFFs en base)
"""
import os, sys, traceback, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

RESULTS = []

def ok(name, detail=""):
    RESULTS.append(("OK", name, detail))
    print(f"  [OK]   {name}")
    if detail: print(f"         {detail}")

def fail(name, detail=""):
    RESULTS.append(("FAIL", name, detail))
    print(f"  [FAIL] {name}")
    if detail: print(f"         {detail[:300]}")

def warn(name, detail=""):
    RESULTS.append(("WARN", name, detail))
    print(f"  [WARN] {name}")
    if detail: print(f"         {detail[:300]}")

print("\n=== TEST PIPE_REAL : Pipeline sur données Sentinel-2 réelles ===\n")

# Charger T1 et T2 depuis la base
from module1_urbanisme.models import ImageSatellite
images = list(ImageSatellite.objects.order_by('date_acquisition'))
if len(images) < 2:
    print("FATAL : Moins de 2 images en base — tests annulés")
    sys.exit(1)

T1, T2 = images[0], images[-1]
print(f"  T1 = {T1.date_acquisition} (ID={T1.id})")
print(f"  T2 = {T2.date_acquisition} (ID={T2.id})\n")

# ── PIPE_REAL-01 : NDBI sur données réelles ──────────────────────────────────
try:
    import rasterio
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    
    ndbi_t1 = calc.calculate_ndbi(T1.bands['B08'], T1.bands['B11'])
    ndbi_t2 = calc.calculate_ndbi(T2.bands['B08'], T2.bands['B11'])
    
    assert ndbi_t1.shape == ndbi_t2.shape, f"Shapes incompatibles : T1={ndbi_t1.shape} T2={ndbi_t2.shape}"
    assert not np.any(np.isinf(ndbi_t1)), "Inf dans NDBI T1"
    assert not np.any(np.isinf(ndbi_t2)), "Inf dans NDBI T2"
    
    t1_stats = f"min={ndbi_t1.min():.3f} max={ndbi_t1.max():.3f} mean={ndbi_t1.mean():.3f}"
    t2_stats = f"min={ndbi_t2.min():.3f} max={ndbi_t2.max():.3f} mean={ndbi_t2.mean():.3f}"
    
    pct_built_t1 = np.mean(ndbi_t1 > 0.2) * 100
    pct_built_t2 = np.mean(ndbi_t2 > 0.2) * 100
    
    ok(f"PIPE_REAL-01 : NDBI T1 {T1.date_acquisition} — {t1_stats} | >0.2 : {pct_built_t1:.1f}%")
    ok(f"PIPE_REAL-01 : NDBI T2 {T2.date_acquisition} — {t2_stats} | >0.2 : {pct_built_t2:.1f}%")
    
    # Seuils vs contexte ivoirien
    if ndbi_t1.max() < 0.2:
        warn("PIPE_REAL-01 : NDBI T1 max < 0.2 — aucun pixel bâti détectable avec le seuil actuel !")
    if ndbi_t2.max() < 0.2:
        warn("PIPE_REAL-01 : NDBI T2 max < 0.2 — aucune construction détectable !")
except Exception as e:
    fail("PIPE_REAL-01 : NDBI réel", traceback.format_exc()[-300:])
    ndbi_t1 = ndbi_t2 = None

# ── PIPE_REAL-02 : NDVI sur données réelles ──────────────────────────────────
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    ndvi_t2 = calc.calculate_ndvi(T2.bands['B04'], T2.bands['B08'])
    
    pct_vegetation = np.mean(ndvi_t2 > 0.4) * 100
    ok(f"PIPE_REAL-02 : NDVI T2 — min={ndvi_t2.min():.3f} max={ndvi_t2.max():.3f} | >0.4 (végétation) : {pct_vegetation:.1f}%")
    
    if pct_vegetation > 40:
        warn(f"PIPE_REAL-02 : {pct_vegetation:.0f}% pixels végétation — masque NDVI important")
except Exception as e:
    fail("PIPE_REAL-02 : NDVI réel", traceback.format_exc()[-300:])
    ndvi_t2 = None

# ── PIPE_REAL-03 : BSI — identique à NDBI ? ──────────────────────────────────
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    bsi_t2 = calc.calculate_bsi(T2.bands['B04'], T2.bands['B08'], T2.bands['B11'])
    
    if ndbi_t2 is not None:
        are_identical = np.allclose(ndbi_t2, bsi_t2, atol=1e-6)
        if are_identical:
            warn("PIPE_REAL-03 : BSI == NDBI sur données RÉELLES (B04 totalement ignoré, formule identique)",
                 f"NDBI mean={ndbi_t2.mean():.4f} vs BSI mean={bsi_t2.mean():.4f} — différence max={abs(ndbi_t2-bsi_t2).max():.8f}")
        else:
            ok(f"PIPE_REAL-03 : BSI ≠ NDBI — diff max={abs(ndbi_t2-bsi_t2).max():.4f}")
    else:
        ok(f"PIPE_REAL-03 : BSI T2 calculé — min={bsi_t2.min():.3f} max={bsi_t2.max():.3f}")
except Exception as e:
    fail("PIPE_REAL-03 : BSI réel", traceback.format_exc()[-300:])
    bsi_t2 = None

# ── PIPE_REAL-04 : Division par zéro protection ──────────────────────────────
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    import tempfile, rasterio
    from rasterio.transform import from_bounds
    calc = NDBICalculator()
    
    # Tableau de zéros = dénominateur nul (B08=B11=0)
    zeros = np.zeros((10, 10), dtype=np.float32)
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = {'driver': 'GTiff', 'height': 10, 'width': 10, 'count': 1,
                   'dtype': 'float32', 'crs': 'EPSG:4326',
                   'transform': from_bounds(-4.03, 5.28, -3.97, 5.32, 10, 10)}
        b08_p = os.path.join(tmpdir, 'B08.tif')
        b11_p = os.path.join(tmpdir, 'B11.tif')
        with rasterio.open(b08_p, 'w', **profile) as dst: dst.write(zeros, 1)
        with rasterio.open(b11_p, 'w', **profile) as dst: dst.write(zeros, 1)
        ndbi_zero = calc.calculate_ndbi(b08_p, b11_p)
    
    assert not np.any(np.isinf(ndbi_zero)), f"Inf présents ! {ndbi_zero}"
    assert not np.any(np.isnan(ndbi_zero)), f"NaN présents ! {ndbi_zero}"
    zero_val = ndbi_zero[0, 0]
    ok(f"PIPE_REAL-04 : Division par zéro protégée — valeur retournée : {zero_val} (attendu 0.0)")
except Exception as e:
    fail("PIPE_REAL-04 : Protection division zéro", traceback.format_exc()[-300:])

# ── PIPE_REAL-05 : Masquage SCL (nuages) ─────────────────────────────────────
try:
    import rasterio
    scl_path = T2.classification_map
    if not scl_path or not os.path.exists(scl_path):
        warn("PIPE_REAL-05 : SCL (classification_map) absent pour T2 — masquage nuages impossible")
    else:
        with rasterio.open(scl_path) as src:
            scl = src.read(1)
        total = scl.size
        cloud_mask = np.isin(scl, [3, 8, 9, 10])  # ombres + nuages
        water_mask = scl == 6
        valid_mask = ~cloud_mask & ~water_mask
        pct_cloud = np.mean(cloud_mask) * 100
        pct_water = np.mean(water_mask) * 100
        pct_valid = np.mean(valid_mask) * 100
        
        ok(f"PIPE_REAL-05 : SCL T2 — nuages/ombres : {pct_cloud:.1f}% | eau : {pct_water:.1f}% | valides : {pct_valid:.1f}%")
        
        if pct_valid < 50:
            fail(f"PIPE_REAL-05 : Seulement {pct_valid:.0f}% pixels valides après masque SCL — image trop nuageuse !")
        elif pct_valid < 70:
            warn(f"PIPE_REAL-05 : {pct_valid:.0f}% pixels valides — couverture nuageuse significative")
except Exception as e:
    fail("PIPE_REAL-05 : Masquage SCL", traceback.format_exc()[-300:])

# ── PIPE_REAL-06 : Détection changements (delta NDBI) ────────────────────────
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    
    if ndbi_t1 is None or ndbi_t2 is None:
        warn("PIPE_REAL-06 : NDBI non disponible — test ignoré")
    else:
        result = calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2=bsi_t2, ndvi_t2=ndvi_t2)
        
        n_new = int(np.sum(result['new_constructions']))
        n_soil = int(np.sum(result['soil_activity']))
        n_demo = int(np.sum(result['demolished']))
        total_px = ndbi_t1.size
        
        ok(f"PIPE_REAL-06 : Nouvelles constructions : {n_new:,} px ({n_new/total_px*100:.2f}%)")
        ok(f"PIPE_REAL-06 : Activité sol (terrassements) : {n_soil:,} px ({n_soil/total_px*100:.2f}%)")
        ok(f"PIPE_REAL-06 : Démolitions : {n_demo:,} px ({n_demo/total_px*100:.2f}%)")
        
        if n_new == 0 and n_soil == 0:
            warn("PIPE_REAL-06 : AUCUN changement détecté — seuils peut-être trop élevés pour Treichville ?")
        
        # Vérifier les artefacts (>5% de pixels = suspect)
        if n_new / total_px > 0.05:
            warn(f"PIPE_REAL-06 : {n_new/total_px*100:.1f}% pixels en construction → artefacts probables")
        
        # Sauvegarder pour PIPE_REAL-07
        change_result = result
except Exception as e:
    fail("PIPE_REAL-06 : detect_changes réel", traceback.format_exc()[-300:])
    change_result = None

# ── PIPE_REAL-07 : extract_change_regions sur données réelles ────────────────
try:
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    
    if change_result is None:
        warn("PIPE_REAL-07 : change_result non disponible — test ignoré")
    else:
        regions = calc.extract_change_regions(change_result['all_changes'], min_size=2)
        ok(f"PIPE_REAL-07 : {len(regions)} régions extraites du masque de changement")
        
        if regions:
            sizes = [r['size_pixels'] for r in regions]
            ok(f"PIPE_REAL-07 : Tailles — min={min(sizes)} max={max(sizes)} mean={np.mean(sizes):.1f} px")
            # Vérifier cohérence surface (10m/px → 100m²/px)
            max_surf_m2 = max(sizes) * 100
            ok(f"PIPE_REAL-07 : Plus grande région : {max(sizes)} px ≈ {max_surf_m2:.0f} m²")
except Exception as e:
    fail("PIPE_REAL-07 : extract_change_regions réel", traceback.format_exc()[-300:])

# ── PIPE_REAL-08 : verification_4_couches sur une vraie détection ─────────────
try:
    from module1_urbanisme.models import DetectionConstruction
    from module1_urbanisme.pipeline.verification_4_couches import DetectionPipeline
    
    # Prendre la première détection en base comme cas de test
    sample = DetectionConstruction.objects.filter(geometry__isnull=False).first()
    if not sample:
        warn("PIPE_REAL-08 : Aucune détection avec géométrie — test ignoré")
    else:
        pipeline = DetectionPipeline()
        region = {
            'centroid': (200, 300),
            'size_pixels': int(sample.surface_m2 / 100) if sample.surface_m2 else 10,
            'bbox': (195, 295, 205, 305),
            'change_type': 'new_construction',
            'ndbi_t1': sample.ndbi_t1,
            'ndbi_t2': sample.ndbi_t2,
            'bsi': sample.bsi_value or 0.2,
            'geometry_geojson': sample.geometry_geojson,
            'confidence': sample.confidence,
        }
        result = pipeline.verify_detection(region)
        ok(f"PIPE_REAL-08 : verify_detection() → status='{result.get('status')}' conf={result.get('confidence', 0):.3f}")
        
        layers = result.get('layers_checked', [])
        ok(f"PIPE_REAL-08 : Couches vérifiées : {layers}")
        
        if len(layers) < 2:
            warn(f"PIPE_REAL-08 : Seulement {len(layers)} couche(s) vérifiée(s) (attendu 4)")
except Exception as e:
    fail("PIPE_REAL-08 : verification_4_couches réel", traceback.format_exc()[-300:])

# ── PIPE_REAL-09 : b03_synthesizer sur données réelles ───────────────────────
try:
    from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        b03_out = os.path.join(tmpdir, "B03_synth.tif")
        result_path = synthesize_b03(T2.bands['B04'], T2.bands['B08'], b03_out)
        
        if result_path and os.path.exists(result_path):
            import rasterio
            with rasterio.open(result_path) as src:
                b03 = src.read(1)
            minv, maxv = float(b03.min()), float(b03.max())
            ok(f"PIPE_REAL-09 : B03 synthétisé — min={minv:.4f} max={maxv:.4f} shape={b03.shape}")
            if maxv > 1.0:
                fail(f"PIPE_REAL-09 : B03 synthétisé max={maxv:.4f} > 1.0 — clip non appliqué !")
            if minv < 0.0:
                warn(f"PIPE_REAL-09 : B03 synthétisé min={minv:.4f} < 0.0 — valeurs négatives")
        else:
            fail("PIPE_REAL-09 : synthesize_b03() n'a pas produit de fichier")
except Exception as e:
    fail("PIPE_REAL-09 : b03_synthesizer réel", traceback.format_exc()[-300:])

# ── PIPE_REAL-10 : Cohérence seuils ndbi_calculator vs verification_4_couches ─
try:
    import inspect
    from module1_urbanisme.pipeline import ndbi_calculator, verification_4_couches
    
    src_ndbi = inspect.getsource(ndbi_calculator)
    src_verif = inspect.getsource(verification_4_couches)
    
    # Chercher les seuils NDBI dans chaque fichier
    import re
    thresholds_ndbi  = re.findall(r'threshold_built\s*=\s*([\d.]+)', src_ndbi)
    thresholds_verif = re.findall(r'ndbi.*?>\s*([\d.]+)', src_verif)
    
    ok(f"PIPE_REAL-10 : ndbi_calculator threshold_built = {thresholds_ndbi}")
    ok(f"PIPE_REAL-10 : verification_4_couches seuils NDBI mentionnés : {list(set(thresholds_verif))[:6]}")
    
    if thresholds_ndbi and '0.2' not in thresholds_ndbi[0] and '0.20' not in thresholds_ndbi[0]:
        warn(f"PIPE_REAL-10 : Seuil ndbi_calculator = {thresholds_ndbi[0]} (attendu 0.2)")
except Exception as e:
    warn("PIPE_REAL-10 : Comparaison seuils", str(e)[:150])

print("\n--- RÉSUMÉ PIPE_REAL ---")
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {nb_ok+nb_warn+nb_fail}")
