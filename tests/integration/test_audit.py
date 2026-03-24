"""
Script de test complet pour l'audit du Module 1 Urbanisme.
Teste chaque étape du pipeline avec les vrais fichiers et la vraie base de données.
"""
import os
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import numpy as np

PASS = 0
FAIL = 0
WARN = 0
results = []

def test(name, func):
    global PASS, FAIL, WARN
    try:
        result = func()
        if result is True:
            PASS += 1
            results.append(f"  [PASS] {name}")
        elif result == "WARN":
            WARN += 1
            results.append(f"  [WARN] {name}")
        else:
            FAIL += 1
            results.append(f"  [FAIL] {name} -> {result}")
    except Exception as e:
        FAIL += 1
        results.append(f"  [FAIL] {name} -> EXCEPTION: {e}")
        traceback.print_exc()

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 0 — Config Django et DB
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 0 — Configuration Django et Base de Données")
print("="*70)

def test_django_config():
    from django.conf import settings
    assert settings.DEBUG is True, f"DEBUG={settings.DEBUG}"
    assert 'module1_urbanisme' in settings.INSTALLED_APPS
    assert 'rest_framework' in settings.INSTALLED_APPS
    assert 'django.contrib.gis' in settings.INSTALLED_APPS
    return True

def test_db_connection():
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
    return True if row[0] == 1 else f"DB returned {row}"

def test_postgis():
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT PostGIS_Version()")
        row = cursor.fetchone()
        print(f"    PostGIS version: {row[0]}")
    return True

def test_models_exist():
    from module1_urbanisme.models import ImageSatellite, ZoneCadastrale, MicrosoftFootprint, DetectionConstruction
    counts = {
        'ImageSatellite': ImageSatellite.objects.count(),
        'ZoneCadastrale': ZoneCadastrale.objects.count(),
        'MicrosoftFootprint': MicrosoftFootprint.objects.count(),
        'DetectionConstruction': DetectionConstruction.objects.count(),
    }
    for k, v in counts.items():
        print(f"    {k}: {v} enregistrements")
    return True

test("Django config loads correctly", test_django_config)
test("Database connection (PostgreSQL)", test_db_connection)
test("PostGIS extension available", test_postgis)
test("All 4 models accessible + counts", test_models_exist)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 0b — Fichiers TIFF locaux
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 0b — Fichiers TIFF locaux (format, bandes, shapes)")
print("="*70)

def test_tiff_files_exist():
    import rasterio
    data_dir = os.path.join(os.path.dirname(__file__), 'module1_urbanisme', 'data_use')
    if not os.path.isdir(data_dir):
        return f"data_use directory not found: {data_dir}"
    
    tiff_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith('.tif') or f.endswith('.tiff'):
                tiff_files.append(os.path.join(root, f))
    
    print(f"    Found {len(tiff_files)} TIFF files in data_use/")
    for tf in sorted(tiff_files):
        rel = os.path.relpath(tf, data_dir)
        try:
            with rasterio.open(tf) as src:
                print(f"    {rel}: {src.width}x{src.height}, {src.count} band(s), dtype={src.dtypes[0]}, crs={src.crs}")
        except Exception as e:
            print(f"    {rel}: ERROR opening - {e}")
    
    return True if len(tiff_files) > 0 else "No TIFF files found"

def test_tiff_bands_readable():
    import rasterio
    data_dir = os.path.join(os.path.dirname(__file__), 'module1_urbanisme', 'data_use')
    errors = []
    
    for root, dirs, files in os.walk(data_dir):
        for f in sorted(files):
            if not (f.endswith('.tif') or f.endswith('.tiff')):
                continue
            fp = os.path.join(root, f)
            try:
                with rasterio.open(fp) as src:
                    data = src.read(1)
                    mn, mx, mean = float(np.nanmin(data)), float(np.nanmax(data)), float(np.nanmean(data))
                    has_nan = bool(np.isnan(data).any())
                    pct_zero = float((data == 0).sum()) / data.size * 100
                    rel = os.path.relpath(fp, data_dir)
                    print(f"    {rel}: min={mn:.4f} max={mx:.4f} mean={mean:.4f} nan={has_nan} zero={pct_zero:.1f}%")
                    if mx == 0 and mn == 0:
                        errors.append(f"{rel}: ALL ZEROS")
            except Exception as e:
                errors.append(f"{f}: {e}")
    
    if errors:
        return f"Errors: {errors}"
    return True

def test_tiff_shapes_consistent():
    import rasterio
    data_dir = os.path.join(os.path.dirname(__file__), 'module1_urbanisme', 'data_use')
    shapes_by_date = {}
    
    for root, dirs, files in os.walk(data_dir):
        for f in sorted(files):
            if not f.endswith('.tif'):
                continue
            # Extract date from filename like B04_2024-02-15.tif
            parts = f.replace('.tif', '').split('_')
            date_str = None
            for p in parts:
                if len(p) == 10 and p[4] == '-':
                    date_str = p
                    break
            if not date_str:
                continue
            
            fp = os.path.join(root, f)
            try:
                with rasterio.open(fp) as src:
                    if date_str not in shapes_by_date:
                        shapes_by_date[date_str] = {}
                    shapes_by_date[date_str][f] = (src.width, src.height)
            except:
                pass
    
    for date, files_shapes in shapes_by_date.items():
        shapes = set(files_shapes.values())
        if len(shapes) > 1:
            print(f"    WARNING: Inconsistent shapes for date {date}:")
            for fn, sh in files_shapes.items():
                print(f"      {fn}: {sh}")
            return f"Inconsistent shapes for {date}"
        else:
            sh = list(shapes)[0]
            print(f"    Date {date}: all {len(files_shapes)} bands are {sh[0]}x{sh[1]} — consistent")
    
    return True

test("TIFF files exist and openable with rasterio", test_tiff_files_exist)
test("TIFF bands readable (min/max/mean/nan/zeros)", test_tiff_bands_readable)
test("TIFF shapes consistent per date", test_tiff_shapes_consistent)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — ImageSatellite en base + chemins valides
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 1 — Images Sentinel en base de données")
print("="*70)

def test_images_in_db():
    from module1_urbanisme.models import ImageSatellite
    imgs = ImageSatellite.objects.all().order_by('date_acquisition')
    if imgs.count() < 2:
        return f"Only {imgs.count()} images in DB, need at least 2"
    
    for img in imgs:
        print(f"    Image ID={img.id}, date={img.date_acquisition}, satellite={img.satellite}")
        print(f"      processed={img.processed}")
        print(f"      bands={img.bands}")
        scl = str(img.classification_map) if img.classification_map else "None"
        print(f"      classification_map={scl}")
        
        # Check band file paths exist
        if img.bands:
            for band_name, band_path in img.bands.items():
                exists = os.path.isfile(band_path)
                print(f"      {band_name}: {'EXISTS' if exists else 'MISSING'} -> {band_path}")
                if not exists:
                    return f"Band file missing: {band_path}"
        
        # Check SCL path
        if img.classification_map:
            scl_path = str(img.classification_map)
            if scl_path and not os.path.isfile(scl_path):
                # Try with name attribute
                scl_path2 = getattr(img.classification_map, 'name', scl_path)
                if not os.path.isfile(scl_path2):
                    print(f"      SCL: MISSING (tried {scl_path} and {scl_path2})")
    
    return True

test("ImageSatellite records with valid band paths", test_images_in_db)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 2A — NDBI Calculator
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 2A — NDBI Calculator (seuillage empirique)")
print("="*70)

def test_ndbi_calculator_import():
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    calc = NDBICalculator()
    print(f"    NDBICalculator created successfully")
    print(f"    Methods: {[m for m in dir(calc) if not m.startswith('_')]}")
    return True

def test_ndbi_calculation():
    import rasterio
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    from module1_urbanisme.models import ImageSatellite
    
    calc = NDBICalculator()
    imgs = ImageSatellite.objects.all().order_by('date_acquisition')
    if imgs.count() < 1:
        return "No images in DB"
    
    img = imgs.first()
    b08_path = img.bands.get('B08')
    b11_path = img.bands.get('B11')
    
    if not b08_path or not b11_path:
        return f"Missing B08 or B11 for image {img.id}"
    
    # Test NDBI calculation
    ndbi = calc.calculate_ndbi(b08_path, b11_path)
    print(f"    NDBI shape: {ndbi.shape}")
    print(f"    NDBI min={np.nanmin(ndbi):.4f} max={np.nanmax(ndbi):.4f} mean={np.nanmean(ndbi):.4f}")
    print(f"    NDBI nan count: {np.isnan(ndbi).sum()} / {ndbi.size}")
    
    # Verify NDBI is in [-1, 1] range
    valid = ndbi[~np.isnan(ndbi)]
    if len(valid) > 0:
        if valid.min() < -1.01 or valid.max() > 1.01:
            return f"NDBI out of range: [{valid.min()}, {valid.max()}]"
    
    return True

def test_ndbi_detect_changes():
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    from module1_urbanisme.models import ImageSatellite
    
    calc = NDBICalculator()
    imgs = ImageSatellite.objects.all().order_by('date_acquisition')
    if imgs.count() < 2:
        return "Need 2 images"
    
    img_t1 = imgs.first()
    img_t2 = imgs.last()
    
    # Calculate NDBI for both
    ndbi_t1 = calc.calculate_ndbi(img_t1.bands['B08'], img_t1.bands['B11'])
    ndbi_t2 = calc.calculate_ndbi(img_t2.bands['B08'], img_t2.bands['B11'])
    
    print(f"    T1 ({img_t1.date_acquisition}): NDBI mean={np.nanmean(ndbi_t1):.4f}")
    print(f"    T2 ({img_t2.date_acquisition}): NDBI mean={np.nanmean(ndbi_t2):.4f}")
    
    if ndbi_t1.shape != ndbi_t2.shape:
        return f"Shape mismatch: T1={ndbi_t1.shape} vs T2={ndbi_t2.shape}"
    
    # Detect changes
    results = calc.detect_changes(ndbi_t1, ndbi_t2)
    print(f"    detect_changes keys: {list(results.keys())}")
    
    mask = results.get('change_mask')
    if mask is not None:
        changed_pix = np.sum(mask > 0)
        total_pix = mask.size
        print(f"    Change mask: {changed_pix} changed pixels / {total_pix} total ({100*changed_pix/total_pix:.2f}%)")
    
    return True

test("NDBICalculator import", test_ndbi_calculator_import)
test("NDBI calculation on real TIFF", test_ndbi_calculation)
test("NDBI detect_changes T1 vs T2", test_ndbi_detect_changes)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 2B — K-Means AI Detector
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 2B — K-Means AI Detector")
print("="*70)

def test_ai_detector_import():
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    det = AIDetector()
    print(f"    AIDetector created, n_clusters={det.n_clusters}")
    return True

def test_ai_detector_predict():
    import rasterio
    from module1_urbanisme.pipeline.ai_detector import AIDetector
    from module1_urbanisme.models import ImageSatellite
    
    det = AIDetector()
    img = ImageSatellite.objects.all().order_by('date_acquisition').last()
    
    b04_path = img.bands.get('B04')
    b08_path = img.bands.get('B08')
    b11_path = img.bands.get('B11')
    
    with rasterio.open(b04_path) as src:
        b04 = src.read(1).astype(np.float32)
    with rasterio.open(b08_path) as src:
        b08 = src.read(1).astype(np.float32)
    with rasterio.open(b11_path) as src:
        b11 = src.read(1).astype(np.float32)
    
    # Resize b11 to match b04/b08 if needed
    if b11.shape != b04.shape:
        from scipy.ndimage import zoom
        factor_h = b04.shape[0] / b11.shape[0]
        factor_w = b04.shape[1] / b11.shape[1]
        b11 = zoom(b11, (factor_h, factor_w), order=1)
        print(f"    Resized B11 to match B04: {b11.shape}")
    
    print(f"    B04: {b04.shape}, B08: {b08.shape}, B11: {b11.shape}")
    
    mask, segmented = det.predict_buildings(b04, b08, b11)
    built_pix = np.sum(mask > 0)
    print(f"    Built mask: {built_pix} pixels classified as built / {mask.size} total ({100*built_pix/mask.size:.2f}%)")
    print(f"    Segmented clusters: {np.unique(segmented).tolist()}")
    
    return True

test("AIDetector import", test_ai_detector_import)
test("AIDetector predict_buildings on real data", test_ai_detector_predict)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 2C — TinyCD Deep Learning
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 2C — TinyCD Deep Learning Detector")
print("="*70)

def test_torch_import():
    import torch
    print(f"    PyTorch version: {torch.__version__}")
    print(f"    CUDA available: {torch.cuda.is_available()}")
    return True

def test_tinycd_model_load():
    from module1_urbanisme.pipeline.deep_learning_detector import DeepLearningDetector
    det = DeepLearningDetector()
    if det.model is None:
        return "Model failed to load (det.model is None)"
    print(f"    Model loaded successfully")
    print(f"    Model type: {type(det.model).__name__}")
    
    # Count parameters
    total_params = sum(p.numel() for p in det.model.parameters())
    trained_params = sum(p.numel() for p in det.model.parameters() if p.requires_grad)
    print(f"    Total parameters: {total_params:,}")
    print(f"    Trainable parameters: {trained_params:,}")
    
    # Check weights file size
    weights_path = os.path.join(os.path.dirname(__file__), 'module1_urbanisme', 'data_use', 'weights', 'model_weights.pth')
    if os.path.exists(weights_path):
        size_mb = os.path.getsize(weights_path) / (1024*1024)
        print(f"    Weights file size: {size_mb:.2f} MB")
        if size_mb < 5:
            print(f"    WARNING: Weights file suspiciously small for {total_params:,} params (expected ~{total_params*4/1024/1024:.0f} MB)")
            return "WARN"
    
    return True

def test_tinycd_inference():
    from module1_urbanisme.pipeline.deep_learning_detector import DeepLearningDetector
    
    det = DeepLearningDetector()
    if det.model is None:
        return "Model not loaded"
    
    # Create small test arrays (3 bands, 64x64)
    t1 = np.random.rand(64, 64, 3).astype(np.float32)
    t2 = np.random.rand(64, 64, 3).astype(np.float32)
    
    mask = det.detect(t1, t2)
    print(f"    Output mask shape: {mask.shape}")
    print(f"    Output mask unique values: {np.unique(mask).tolist()}")
    print(f"    Changed pixels: {np.sum(mask > 0)} / {mask.size}")
    
    return True

test("PyTorch import", test_torch_import)
test("TinyCD model load + weight check", test_tinycd_model_load)
test("TinyCD inference (synthetic data)", test_tinycd_inference)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Extract regions
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 3 — Extraction régions et conversion GPS")
print("="*70)

def test_extract_regions():
    from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
    from module1_urbanisme.models import ImageSatellite
    
    calc = NDBICalculator()
    imgs = ImageSatellite.objects.all().order_by('date_acquisition')
    if imgs.count() < 2:
        return "Need 2 images"
    
    img_t1 = imgs.first()
    img_t2 = imgs.last()
    
    ndbi_t1 = calc.calculate_ndbi(img_t1.bands['B08'], img_t1.bands['B11'])
    ndbi_t2 = calc.calculate_ndbi(img_t2.bands['B08'], img_t2.bands['B11'])
    results = calc.detect_changes(ndbi_t1, ndbi_t2)
    
    regions = calc.extract_change_regions(results, min_size=2)
    print(f"    Extracted {len(regions)} change regions (min_size=2)")
    
    if len(regions) > 0:
        r = regions[0]
        print(f"    First region keys: {list(r.keys())}")
        print(f"    First region: centroid=({r.get('centroid_row')},{r.get('centroid_col')}), size={r.get('size_pixels')} px")
    
    return True

test("Extract change regions from NDBI", test_extract_regions)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — SAR Module
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 4 — Module SAR Sentinel-1")
print("="*70)

def test_sar_import():
    from module1_urbanisme.pipeline.sentinel1_sar import evaluate_sar_backscatter_delta, merge_optical_and_sar_masks
    print(f"    SAR functions imported OK: evaluate_sar_backscatter_delta, merge_optical_and_sar_masks")
    return True

def test_sar_placeholder():
    from module1_urbanisme.pipeline.sentinel1_sar import fetch_and_evaluate_sar_for_bbox
    # Function signature: (sh_config, bbox_wgs84, date_t1, date_t2)
    result = fetch_and_evaluate_sar_for_bbox(None, [-4.03, 5.28, -3.97, 5.32], "2024-01-01", "2025-01-01")
    print(f"    fetch result: {result}")
    if result.get('sar_detected') is False:
        print(f"    CONFIRMED: SAR is a placeholder (not functional)")
        return "WARN"
    return True

def test_sar_algorithm():
    from module1_urbanisme.pipeline.sentinel1_sar import evaluate_sar_backscatter_delta
    vv_t1 = np.random.rand(100, 100).astype(np.float32) * 0.5
    vv_t2 = vv_t1 + np.random.rand(100, 100).astype(np.float32) * 0.3
    vh_t1 = np.random.rand(100, 100).astype(np.float32) * 0.3
    vh_t2 = vh_t1.copy()
    
    mask = evaluate_sar_backscatter_delta(vv_t1, vv_t2, vh_t1, vh_t2)
    print(f"    SAR mask shape: {mask.shape}, detected: {np.sum(mask>0)} pixels")
    return True

test("SAR module import", test_sar_import)
test("SAR fetch_and_evaluate (placeholder check)", test_sar_placeholder)
test("SAR backscatter delta algorithm (synthetic)", test_sar_algorithm)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — HuggingFace AI Client
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 5 — HuggingFace AI Client")
print("="*70)

def test_hf_import():
    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
    client = HuggingFaceAIClient()
    print(f"    HF client created")
    print(f"    is_available: {client.is_available()}")
    print(f"    Token present: {bool(os.environ.get('HUGGINGFACE_TOKEN', ''))}")
    return True

def test_hf_local_scoring():
    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
    client = HuggingFaceAIClient()
    
    # Create fake NDBI data
    ndbi_t1 = np.random.rand(100, 100).astype(np.float32) * 0.2
    ndbi_t2 = ndbi_t1 + 0.15  # Simulate construction (NDBI increase)
    
    score = client._local_ai_score(ndbi_t1, ndbi_t2)
    print(f"    Local AI score (simulated construction): {score}")
    
    if not (0.0 <= score <= 1.0):
        return f"Score out of range: {score}"
    
    return True

test("HuggingFace client import + availability", test_hf_import)
test("HuggingFace local AI scoring", test_hf_local_scoring)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Croisement cadastral
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 6 — Croisement cadastral et vérification 4 couches")
print("="*70)

def test_cadastre_data():
    from module1_urbanisme.models import ZoneCadastrale
    count = ZoneCadastrale.objects.count()
    if count == 0:
        print(f"    No cadastral zones in DB — need to run import_cadastre first")
        return "WARN"
    
    print(f"    {count} zones cadastrales en base")
    stats = {}
    for z in ZoneCadastrale.objects.all():
        status = z.buildable_status
        stats[status] = stats.get(status, 0) + 1
        has_geom = z.geometry is not None
        if not has_geom:
            print(f"    WARNING: Zone {z.zone_id} has NO geometry")
    
    for status, cnt in stats.items():
        print(f"    {status}: {cnt} zones")
    
    return True

def test_microsoft_data():
    from module1_urbanisme.models import MicrosoftFootprint
    count = MicrosoftFootprint.objects.count()
    if count == 0:
        print(f"    No Microsoft footprints in DB — need to run import_microsoft first")
        return "WARN"
    
    print(f"    {count} empreintes Microsoft en base")
    # Check a sample has geometry
    sample = MicrosoftFootprint.objects.first()
    if sample:
        has_geom = sample.geometry is not None
        print(f"    Sample footprint has geometry: {has_geom}")
    
    return True

def test_verification_4couches_import():
    from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches
    v = Verification4Couches()
    print(f"    Verification4Couches created OK")
    print(f"    Methods: {[m for m in dir(v) if not m.startswith('_') and callable(getattr(v, m))]}")
    return True

test("Cadastral zones in DB", test_cadastre_data)
test("Microsoft footprints in DB", test_microsoft_data)
test("Verification4Couches import", test_verification_4couches_import)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — API Health Checker
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 7 — API Health Checker")
print("="*70)

def test_health_checker():
    from module1_urbanisme.pipeline.api_health_checker import APIHealthChecker
    checker = APIHealthChecker()
    results_check = checker.run_all_checks()
    print(f"    Results keys: {list(results_check.keys())}")
    # results values are booleans (True/False), not dicts
    for k, v in results_check.items():
        status = 'AVAILABLE' if v else 'UNAVAILABLE'
        print(f"    {k}: {status}")
    return True

def test_health_checker_minimum():
    from module1_urbanisme.pipeline.api_health_checker import APIHealthChecker
    checker = APIHealthChecker()
    checker.run_all_checks()
    try:
        checker.assert_minimum_viable()
        print(f"    assert_minimum_viable: PASSED")
        return True
    except Exception as e:
        print(f"    assert_minimum_viable: FAILED - {e}")
        return f"Minimum viable check failed: {e}"

test("API Health Checker run_all_checks", test_health_checker)
test("API Health Checker assert_minimum_viable", test_health_checker_minimum)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 8 — B03 Synthesizer
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 8 — B03 Synthesizer")
print("="*70)

def test_b03_synthesizer():
    from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
    from module1_urbanisme.models import ImageSatellite
    
    img = ImageSatellite.objects.all().order_by('date_acquisition').first()
    if not img:
        return "No images in DB"
    
    b04_path = img.bands.get('B04')
    b08_path = img.bands.get('B08')
    if not b04_path or not b08_path:
        return "Missing B04 or B08"
    
    output = os.path.join(os.path.dirname(__file__), 'module1_urbanisme', 'data_use', 'test_b03_synth.tif')
    result = synthesize_b03(b04_path, b08_path, output)
    
    if result and os.path.exists(result):
        import rasterio
        with rasterio.open(result) as src:
            data = src.read(1)
            print(f"    B03 synth: shape={data.shape}, min={np.nanmin(data):.4f}, max={np.nanmax(data):.4f}, mean={np.nanmean(data):.4f}")
        # Clean up test file
        os.remove(result)
        print(f"    Test file cleaned up")
        return True
    else:
        return f"synthesize_b03 returned: {result}"

test("B03 Synthesizer on real B04/B08", test_b03_synthesizer)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 9 — Django management commands (dry-run)
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 9 — Management commands check")
print("="*70)

def test_management_commands_list():
    from django.core.management import get_commands
    commands = get_commands()
    our_cmds = {k: v for k, v in commands.items() if v == 'module1_urbanisme'}
    print(f"    Module1 commands: {list(our_cmds.keys())}")
    expected = ['import_cadastre', 'import_microsoft', 'import_sentinel', 'import_sentinel_api', 'run_detection']
    missing = [c for c in expected if c not in our_cmds]
    if missing:
        return f"Missing commands: {missing}"
    return True

test("Management commands registered", test_management_commands_list)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 10 — GEE Compositor
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 10 — GEE Compositor")
print("="*70)

def test_gee_import():
    from module1_urbanisme.pipeline.gee_composite import GEECompositor
    try:
        compositor = GEECompositor()
        status = compositor.status()
        print(f"    GEE status: {status}")
        if not status.get('initialized', False):
            print(f"    GEE not initialized (expected without auth)")
            return "WARN"
        return True
    except Exception as e:
        print(f"    GEE init error (expected): {e}")
        return "WARN"

test("GEE Compositor import + status", test_gee_import)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 11 — Sentinel Data Fetcher
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 11 — Sentinel Data Fetcher")
print("="*70)

def test_sentinel_fetcher():
    from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher, TREICHVILLE_BBOX
    print(f"    TREICHVILLE_BBOX: {TREICHVILLE_BBOX}")
    fetcher = SentinelDataFetcher()
    status = fetcher.status()
    print(f"    Fetcher status: {status}")
    return True

test("SentinelDataFetcher import + status", test_sentinel_fetcher)

# ═══════════════════════════════════════════════════════════════════════
# ÉTAPE 12 — API REST (URLs + Views)
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("ÉTAPE 12 — API REST configuration")
print("="*70)

def test_api_urls():
    from django.urls import reverse, resolve
    from django.test import RequestFactory
    
    # Check URL patterns exist
    try:
        from config.urls import urlpatterns
        print(f"    Root URL patterns: {len(urlpatterns)}")
        for p in urlpatterns:
            print(f"      {p.pattern}")
    except Exception as e:
        return f"URL config error: {e}"
    
    return True

test("API URL configuration", test_api_urls)

# ═══════════════════════════════════════════════════════════════════════
# RÉSUMÉ FINAL
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("RÉSUMÉ FINAL")
print("="*70)
for r in results:
    print(r)

print(f"\nTotal: {PASS} PASS, {WARN} WARN, {FAIL} FAIL / {PASS+WARN+FAIL} tests")
print("="*70)
