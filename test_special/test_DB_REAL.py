"""
TEST DB RÉEL — Intégrité des données en base (données réelles, pas simulées)
"""
import os, sys, traceback, json

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

print("\n=== TEST DB_REAL : Intégrité données réelles ===\n")

# ── DB_REAL-01 : Comptage tables ─────────────────────────────────────────────
try:
    from module1_urbanisme.models import ImageSatellite, ZoneCadastrale, MicrosoftFootprint, DetectionConstruction
    counts = {
        'ImageSatellite': ImageSatellite.objects.count(),
        'ZoneCadastrale': ZoneCadastrale.objects.count(),
        'MicrosoftFootprint': MicrosoftFootprint.objects.count(),
        'DetectionConstruction': DetectionConstruction.objects.count(),
    }
    for model, count in counts.items():
        ok(f"DB_REAL-01 : {model}.objects.count() = {count}")
    if counts['ImageSatellite'] == 0:
        fail("DB_REAL-01 : Aucune ImageSatellite — pipeline impossible !")
    if counts['ZoneCadastrale'] == 0:
        fail("DB_REAL-01 : Aucune ZoneCadastrale — vérification 4 couches impossible !")
    if counts['MicrosoftFootprint'] == 0:
        warn("DB_REAL-01 : Aucun MicrosoftFootprint — couche Google Buildings vide")
except Exception as e:
    fail("DB_REAL-01 : Comptage tables", traceback.format_exc()[-200:])

# ── DB_REAL-02 : Intégrité ImageSatellite (fichiers TIFF) ────────────────────
try:
    from module1_urbanisme.models import ImageSatellite
    import rasterio
    images = list(ImageSatellite.objects.all().order_by('date_acquisition'))
    print(f"\n  Analyse {len(images)} ImageSatellite(s)...")
    
    valid_images = []
    for img in images:
        issues = []
        # Vérifier les bandes requises
        bands = img.bands or {}
        for b in ['B04', 'B08', 'B11']:
            if b not in bands:
                issues.append(f"{b} manquante")
            elif not os.path.exists(bands[b]):
                issues.append(f"{b} fichier inexistant : {bands[b]}")
        
        if issues:
            warn(f"DB_REAL-02 : ImageSatellite ID={img.id} date={img.date_acquisition}", str(issues))
        else:
            # Tester lisibilité rasterio pour B08
            try:
                with rasterio.open(bands['B08']) as src:
                    arr = src.read(1)
                    crs = src.crs
                    shape = src.shape
                    minv, maxv = float(arr.min()), float(arr.max())
                ok(f"DB_REAL-02 : ImageSatellite ID={img.id} date={img.date_acquisition} — B08 {shape} min={minv:.4f} max={maxv:.4f} CRS={crs}")
                valid_images.append(img)
            except Exception as e2:
                fail(f"DB_REAL-02 : ImageSatellite ID={img.id} B08 illisible", str(e2)[:150])
    
    if len(valid_images) >= 2:
        ok(f"DB_REAL-02 : {len(valid_images)} images valides → paire T1/T2 possible")
    elif len(valid_images) == 1:
        warn(f"DB_REAL-02 : 1 seule image valide → pas de détection de changement possible")
    else:
        fail("DB_REAL-02 : Aucune image valide — pipeline bloqué !")
except Exception as e:
    fail("DB_REAL-02 : Intégrité ImageSatellite", traceback.format_exc()[-200:])

# ── DB_REAL-03 : Zones cadastrales — géométries et statuts ──────────────────
try:
    from module1_urbanisme.models import ZoneCadastrale
    from django.contrib.gis.geos import Point
    
    zones = ZoneCadastrale.objects.all()
    statuts = list(zones.values_list('buildable_status', flat=True).distinct())
    ok(f"DB_REAL-03 : ZoneCadastrale statuts présents : {statuts}")
    
    for s in ['forbidden', 'conditional', 'buildable']:
        c = zones.filter(buildable_status=s).count()
        if c == 0:
            warn(f"DB_REAL-03 : Aucune zone '{s}' en base")
        else:
            ok(f"DB_REAL-03 : Zone '{s}' → {c} zone(s)")
    
    # Point-dans-polygone sur le centroïde de Treichville
    treichville_center = Point(-4.001, 5.303, srid=4326)
    hits = ZoneCadastrale.objects.filter(geometry__contains=treichville_center)
    if hits.exists():
        z = hits.first()
        ok(f"DB_REAL-03 : Point (-4.001, 5.303) dans zone '{z.zone_id}' ({z.buildable_status})")
    else:
        warn("DB_REAL-03 : Point centroïde Treichville (-4.001, 5.303) hors toutes zones cadastrales")
    
    # Géométries valides
    invalid = 0
    for z in zones:
        if z.geometry and not z.geometry.valid:
            invalid += 1
    if invalid > 0:
        fail(f"DB_REAL-03 : {invalid} géométrie(s) invalide(s) dans ZoneCadastrale !")
    else:
        ok(f"DB_REAL-03 : Toutes les géométries ZoneCadastrale sont valides")

except Exception as e:
    fail("DB_REAL-03 : ZoneCadastrale", traceback.format_exc()[-200:])

# ── DB_REAL-04 : MicrosoftFootprint / Google Buildings ──────────────────────
try:
    from module1_urbanisme.models import MicrosoftFootprint
    total = MicrosoftFootprint.objects.count()
    
    if total == 0:
        warn("DB_REAL-04 : Aucun MicrosoftFootprint en base")
    else:
        sources = list(MicrosoftFootprint.objects.values_list('source', flat=True).distinct())
        ok(f"DB_REAL-04 : {total:,} MicrosoftFootprint — sources : {sources}")
        
        # Distribution confidence_score
        null_conf = MicrosoftFootprint.objects.filter(confidence_score__isnull=True).count()
        high_conf = MicrosoftFootprint.objects.filter(confidence_score__gte=0.75).count()
        med_conf  = MicrosoftFootprint.objects.filter(confidence_score__gte=0.70, confidence_score__lt=0.75).count()
        low_conf  = MicrosoftFootprint.objects.filter(confidence_score__gte=0.65, confidence_score__lt=0.70).count()
        
        ok(f"DB_REAL-04 : confidence_score NULL={null_conf:,} | >=0.75={high_conf:,} | 0.70-0.75={med_conf:,} | 0.65-0.70={low_conf:,}")
        
        if null_conf == total:
            fail(f"DB_REAL-04 : TOUS les confidence_score sont NULL ! Couche Google Buildings inutilisable pour scoring.")
        elif null_conf > total * 0.5:
            warn(f"DB_REAL-04 : {null_conf/total*100:.0f}% des confidence_score sont NULL")
        
        # ST_DWithin test (rayon 15m ≈ 0.000135°)
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import D
        pt = Point(-4.001, 5.303, srid=4326)
        nearby = MicrosoftFootprint.objects.filter(geometry__dwithin=(pt, 0.000135)).count()
        ok(f"DB_REAL-04 : ST_DWithin 15m autour (-4.001, 5.303) → {nearby} bâtiment(s)")
        
        # Vérifier source Microsoft mal étiquetée
        ms_footprints = MicrosoftFootprint.objects.filter(source_file__icontains='Abidjan').count()
        if ms_footprints > 0:
            wrong_src = MicrosoftFootprint.objects.filter(
                source_file__icontains='Abidjan', source='Google_V3_2023'
            ).count()
            if wrong_src > 0:
                warn(f"DB_REAL-04 : {wrong_src:,} empreintes Microsoft (fichier Abidjan) ont source='Google_V3_2023' !")
except Exception as e:
    fail("DB_REAL-04 : MicrosoftFootprint", traceback.format_exc()[-200:])

# ── DB_REAL-05 : Intégrité des DetectionConstruction (échantillon 10) ────────
try:
    from module1_urbanisme.models import DetectionConstruction
    import json as _json
    
    sample = list(DetectionConstruction.objects.order_by('-date_detection')[:10])
    ok(f"DB_REAL-05 : Échantillon de {len(sample)} détection(s) récentes")
    
    issues_total = 0
    TREICH_LON_MIN, TREICH_LON_MAX = -4.04, -3.96
    TREICH_LAT_MIN, TREICH_LAT_MAX = 5.27, 5.33
    
    for d in sample:
        issues = []
        # Confidence
        if not (0.0 <= d.confidence <= 1.0):
            issues.append(f"confidence={d.confidence} hors [0,1]")
        # Status valide
        valid_statuses = [s[0] for s in DetectionConstruction.STATUS_CHOICES]
        if d.status not in valid_statuses:
            issues.append(f"status='{d.status}' invalide")
        # alert_level valide
        valid_levels = [s[0] for s in DetectionConstruction.ALERT_LEVEL_CHOICES]
        if d.alert_level not in valid_levels:
            issues.append(f"alert_level='{d.alert_level}' invalide")
        # Géométrie
        if d.geometry is None:
            issues.append("geometry=NULL")
        elif not d.geometry.valid:
            issues.append("geometry invalide (ST_IsValid=false)")
        else:
            # Vérifier dans BBOX
            lat = d.latitude
            lon = d.longitude
            if lat is None or lon is None:
                issues.append("centroïde None")
            elif not (TREICH_LAT_MIN < lat < TREICH_LAT_MAX and TREICH_LON_MIN < lon < TREICH_LON_MAX):
                issues.append(f"centroïde hors BBOX Treichville: lat={lat:.4f} lon={lon:.4f}")
        # Surface
        if d.surface_m2 is not None and d.surface_m2 <= 0:
            issues.append(f"surface_m2={d.surface_m2} <= 0")
        # geometry_geojson property
        try:
            gj = d.geometry_geojson
            if gj:
                parsed = _json.loads(gj)
                if parsed.get('type') != 'Polygon':
                    issues.append(f"geometry_geojson type={parsed.get('type')} (attendu Polygon)")
        except Exception as pe:
            issues.append(f"geometry_geojson exception: {pe}")
        
        # Alert level cohérence avec status
        coherence = {
            'infraction_zonage': 'rouge',
            'sous_condition': 'orange',
            'conforme': 'vert',
            'surveillance_preventive': 'veille'
        }
        expected_level = coherence.get(d.status)
        if expected_level and d.alert_level != expected_level:
            issues.append(f"incohérence status/alert: {d.status}→{d.alert_level} (attendu {expected_level})")
        
        if issues:
            warn(f"DB_REAL-05 : Détection ID={d.id} status={d.status} conf={d.confidence:.2f}", str(issues))
            issues_total += 1
        else:
            ok(f"DB_REAL-05 : Détection ID={d.id} status={d.status} conf={d.confidence:.2f} lat={d.latitude:.5f} lon={d.longitude:.5f} surf={d.surface_m2:.0f}m²")
    
    if issues_total == 0:
        ok(f"DB_REAL-05 : Tous les {len(sample)} échantillons sont valides")
    else:
        warn(f"DB_REAL-05 : {issues_total}/{len(sample)} détections avec anomalies")

except Exception as e:
    fail("DB_REAL-05 : DetectionConstruction échantillon", traceback.format_exc()[-200:])

# ── DB_REAL-06 : Cohérence T1/T2 (paire d'images formable) ─────────────────
try:
    from module1_urbanisme.models import ImageSatellite
    images = list(ImageSatellite.objects.order_by('date_acquisition'))
    if len(images) >= 2:
        t1, t2 = images[0], images[-1]
        ok(f"DB_REAL-06 : Paire T1={t1.date_acquisition} T2={t2.date_acquisition} ({(t2.date_acquisition - t1.date_acquisition).days} jours d'écart)")
        # Vérifier que les deux ont les mêmes bandes
        b1 = set(t1.bands.keys()) if t1.bands else set()
        b2 = set(t2.bands.keys()) if t2.bands else set()
        common = b1 & b2
        ok(f"DB_REAL-06 : Bandes communes T1∩T2 = {sorted(common)}")
        if 'B08' not in common or 'B11' not in common:
            fail("DB_REAL-06 : B08 ou B11 manquante dans la paire T1/T2 — NDBI impossible !")
    else:
        warn("DB_REAL-06 : Moins de 2 images — pas de paire T1/T2")
except Exception as e:
    fail("DB_REAL-06 : Cohérence T1/T2", str(e)[:200])

# ── DB_REAL-07 : Extension PostGIS installée ─────────────────────────────────
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT postgis_version();")
        row = cursor.fetchone()
        ok(f"DB_REAL-07 : PostGIS version = {row[0]}")
except Exception as e:
    fail("DB_REAL-07 : PostGIS extension", str(e)[:200])

print("\n--- RÉSUMÉ DB_REAL ---")
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {nb_ok+nb_warn+nb_fail}")
