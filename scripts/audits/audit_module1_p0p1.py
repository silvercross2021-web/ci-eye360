import os
import sys
import time
from urllib.error import URLError

import django
from django.core.management import call_command
from io import StringIO

def run_phase_0_1():
    print("=== PHASE 0: PREPARATION ET ETAT DU SYSTEME ===")
    
    # Check 0.2 Database & Migrations
    out = StringIO()
    err = StringIO()
    try:
        call_command('check', '--database', 'default', stdout=out, stderr=err)
        print("0.2 - DB Check: OK")
    except Exception as e:
        print(f"0.2 - DB Check: ERROR - {e}")

    try:
        out = StringIO()
        call_command('showmigrations', stdout=out)
        migrations = out.getvalue()
        pending = [line for line in migrations.split('\n') if '[ ]' in line]
        print(f"0.2 - Migrations pending: {len(pending)}")
        for p in pending:
            print(f"      {p.strip()}")
    except Exception as e:
        print(f"0.2 - Migrations Check: ERROR - {e}")
        
    # Check 0.3 Django Config
    print("\n0.3 - Django Configuration:")
    out = StringIO()
    try:
        call_command('check', stdout=out)
        if not out.getvalue().strip():
            print("      manage.py check: OK (No issues)")
        else:
            print(f"      manage.py check: {out.getvalue().strip()}")
    except Exception as e:
        print(f"      manage.py check: Exception {e}")

    from django.conf import settings
    print(f"      DEBUG: {settings.DEBUG}")
    print(f"      ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    
    # Check dotenv load in settings
    settings_file = os.path.join(settings.BASE_DIR, 'config', 'settings.py')
    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'load_dotenv()' in content:
            print("      load_dotenv() is present in settings.py")
        else:
            print("      load_dotenv() NOT present in settings.py (Good, using environ)")

    # Check 0.4 environment
    print("\n0.4 - Variables d'environnement:")
    keys = ['SENTINEL_HUB_CLIENT_ID', 'GEE_PROJECT_ID', 'HUGGINGFACE_TOKEN']
    for k in keys:
        val = os.environ.get(k)
        print(f"      {k}: {'Set' if val else 'Missing/Empty'}")


    print("\n=== PHASE 1: TESTS DES DONNEES EN BASE ===")
    from module1_urbanisme.models import ImageSatellite, ZoneCadastrale, MicrosoftFootprint, DetectionConstruction
    import rasterio

    # 1.1 Images Sentinel-2
    images = ImageSatellite.objects.all().order_by('-date_acquisition')
    print(f"1.1 - ImageSatellite count: {images.count()}")
    for img in images:
        print(f"      Image {img.id} (Acquisition: {img.date_acquisition}):")
        print(f"        Classification Map: {img.classification_map}")
        for b_name, b_path in img.bands.items():
            exists = os.path.exists(b_path)
            print(f"        Band {b_name}: Exists={exists}, Path={b_path}")
            if exists:
                try:
                    with rasterio.open(b_path) as src:
                        data = src.read(1)
                        print(f"          Valid TIFF: shape={data.shape}, crs={src.crs}, min={data.min()}, max={data.max()}")
                except Exception as e:
                    print(f"          Error reading TIFF: {str(e)}")

    if images.count() >= 2:
        diff_days = (images[0].date_acquisition - images[1].date_acquisition).days
        print(f"      Interval between latest 2 images: {diff_days} days")

    # 1.2 Zones Cadastrales
    zones = ZoneCadastrale.objects.all()
    print(f"\n1.2 - ZoneCadastrale count: {zones.count()}")
    if zones.count() > 0:
        types = set(z.buildable_status for z in zones)
        print(f"      Buildable statuses present: {types}")
        
        # Test point in polygon
        from django.contrib.gis.geos import Point
        pt = Point(-4.001, 5.303, srid=4326) # En plein Treichville
        zone_pt = ZoneCadastrale.objects.filter(geometry__contains=pt).first()
        print(f"      Point in polygon (-4.001, 5.303): {zone_pt.name if zone_pt else 'Not Found'}")

    # 1.3 Microsoft Footprint
    fps = MicrosoftFootprint.objects.all()
    print(f"\n1.3 - MicrosoftFootprint count: {fps.count()}")
    if fps.count() > 0:
        sources = set(f.source for f in fps)
        print(f"      Sources present: {sources}")
        
        # Confidences
        c1 = fps.filter(confidence_score__gte=0.75).count()
        c2 = fps.filter(confidence_score__gte=0.70, confidence_score__lt=0.75).count()
        c3 = fps.filter(confidence_score__gte=0.65, confidence_score__lt=0.70).count()
        print(f"      Confidence >= 0.75: {c1}")
        print(f"      Confidence 0.70-0.75: {c2}")
        print(f"      Confidence 0.65-0.70: {c3}")
        
        # Point query
        from django.contrib.gis.measure import D
        radius_degrees = 15 / 111320.0
        nearby = MicrosoftFootprint.objects.filter(geometry__dwithin=(pt, radius_degrees)).count()
        print(f"      ST_DWithin 15m from (-4.001, 5.303): {nearby} footprints")

    # 1.4 Detections
    dets = DetectionConstruction.objects.all()
    print(f"\n1.4 - DetectionConstruction count: {dets.count()}")
    for det in dets[:5]:
        print(f"      Det {det.id}: status={det.status}, alert={det.alert_level}, conf={det.confidence}, m2={det.surface_m2}, lat={det.latitude}, lon={det.longitude}")
        if det.geometry_geojson:
            print(f"        GeoJSON len: {len(det.geometry_geojson)}")
        else:
            print("        GeoJSON: None or invalid")

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    run_phase_0_1()
