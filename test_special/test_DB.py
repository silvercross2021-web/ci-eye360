"""
TEST DB — Modèles Django, ORM, serializers
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

print("\n=== TEST DB : Modèles et ORM ===\n")

# DB-01 : Django setup
try:
    import django
    django.setup()
    ok("DB-01 : django.setup() OK")
except Exception as e:
    fail("DB-01 : django.setup()", str(e))
    sys.exit(1)

# DB-02 : Connexion à la base de données
try:
    from django.db import connection
    connection.ensure_connection()
    ok("DB-02 : Connexion DB OK")
except Exception as e:
    fail("DB-02 : Connexion DB", str(e)[:200])

# DB-03 : Migrations appliquées (tables existent)
try:
    from django.db import connection
    tables = connection.introspection.table_names()
    expected = [
        'module1_urbanisme_zonecadastrale',
        'module1_urbanisme_imagesatellite',
        'module1_urbanisme_microsoftfootprint',
        'module1_urbanisme_detectionconstruction',
    ]
    missing = [t for t in expected if t not in tables]
    if missing:
        fail("DB-03 : Tables manquantes (migrations non appliquées ?)", str(missing))
    else:
        ok("DB-03 : Toutes les tables existent")
except Exception as e:
    fail("DB-03 : Introspection tables", str(e)[:200])

# DB-04 : ZoneCadastrale.BUILDABLE_STATUS_CHOICES accessible
try:
    from module1_urbanisme.models import ZoneCadastrale
    choices = ZoneCadastrale.BUILDABLE_STATUS_CHOICES
    assert len(choices) > 0
    ok(f"DB-04 : BUILDABLE_STATUS_CHOICES accessible ({len(choices)} choix)")
except AttributeError as e:
    fail("DB-04 : ZoneCadastrale.BUILDABLE_STATUS_CHOICES", "AttributeError — classe variable absente !")
except Exception as e:
    fail("DB-04", str(e)[:200])

# DB-05 : DetectionConstruction.STATUS_CHOICES accessible
try:
    from module1_urbanisme.models import DetectionConstruction
    choices = DetectionConstruction.STATUS_CHOICES
    assert len(choices) > 0
    ok(f"DB-05 : STATUS_CHOICES accessible ({len(choices)} choix)")
except AttributeError:
    fail("DB-05 : DetectionConstruction.STATUS_CHOICES", "AttributeError — views_web.py ligne 70 crashera !")
except Exception as e:
    fail("DB-05", str(e)[:200])

# DB-06 : DetectionConstruction.ALERT_LEVEL_CHOICES accessible
try:
    from module1_urbanisme.models import DetectionConstruction
    choices = DetectionConstruction.ALERT_LEVEL_CHOICES
    assert len(choices) > 0
    ok(f"DB-06 : ALERT_LEVEL_CHOICES accessible ({len(choices)} choix)")
except AttributeError:
    fail("DB-06 : DetectionConstruction.ALERT_LEVEL_CHOICES", "AttributeError — views_web.py ligne 71 crashera !")
except Exception as e:
    fail("DB-06", str(e)[:200])

# DB-07 : geometry_geojson property sur DetectionConstruction (geometry=None)
try:
    from module1_urbanisme.models import DetectionConstruction
    d = DetectionConstruction()  # geometry = None
    d.geometry = None
    result = d.geometry_geojson
    assert result is None, f"geometry_geojson devrait être None quand geometry=None, obtenu: {result}"
    ok("DB-07 : geometry_geojson(None) → None OK")
except Exception as e:
    fail("DB-07 : geometry_geojson property avec geometry=None", traceback.format_exc()[-300:])

# DB-08 : geometry_geojson property sur ZoneCadastrale (geometry=None)
try:
    from module1_urbanisme.models import ZoneCadastrale
    z = ZoneCadastrale()
    z.geometry = None
    result = z.geometry_geojson
    assert result is None
    ok("DB-08 : ZoneCadastrale.geometry_geojson(None) → None OK")
except Exception as e:
    fail("DB-08 : ZoneCadastrale.geometry_geojson avec None", traceback.format_exc()[-300:])

# DB-09 : DetectionCreateSerializer — geometry_geojson READ-ONLY est le comportement correct
# Le champ 'geometry' (PolygonField) est writable, 'geometry_geojson' est juste un display read-only
try:
    from module1_urbanisme.serializers import DetectionCreateSerializer
    serializer = DetectionCreateSerializer()
    fields = serializer.fields
    geometry_writable = 'geometry' in fields and not fields['geometry'].read_only
    geojson_readonly  = 'geometry_geojson' not in fields or fields['geometry_geojson'].read_only
    if geometry_writable and geojson_readonly:
        ok("DB-09 : geometry (PolygonField) writable + geometry_geojson read-only (display) — design correct")
    elif not geometry_writable:
        warn("DB-09 : champ geometry absent ou read-only dans DetectionCreateSerializer")
    else:
        ok(f"DB-09 : DetectionCreateSerializer fields OK")
except Exception as e:
    fail("DB-09 : DetectionCreateSerializer fields", traceback.format_exc()[-300:])

# DB-10 : ordering_fields 'priority_score' dans DetectionConstructionViewSet
try:
    from module1_urbanisme.views import DetectionConstructionViewSet
    ordering_fields = getattr(DetectionConstructionViewSet, 'ordering_fields', [])
    if 'priority_score' in ordering_fields:
        warn("DB-10 : ordering_fields contient 'priority_score' (SerializerMethodField non ORM)",
             "Tri par priority_score via ?ordering=priority_score sera ignoré silencieusement ou crashera")
    else:
        ok("DB-10 : ordering_fields sans priority_score (OK)")
except Exception as e:
    fail("DB-10 : DetectionConstructionViewSet.ordering_fields", str(e)[:200])

# DB-11 : ZoneCadastrale count() sans crash
try:
    from module1_urbanisme.models import ZoneCadastrale
    count = ZoneCadastrale.objects.count()
    ok(f"DB-11 : ZoneCadastrale.objects.count() = {count}")
except Exception as e:
    fail("DB-11 : ZoneCadastrale.objects.count()", str(e)[:200])

# DB-12 : DetectionConstruction count() sans crash
try:
    from module1_urbanisme.models import DetectionConstruction
    count = DetectionConstruction.objects.count()
    ok(f"DB-12 : DetectionConstruction.objects.count() = {count}")
except Exception as e:
    fail("DB-12 : DetectionConstruction.objects.count()", str(e)[:200])

# DB-13 : MicrosoftFootprint — source default correct (Google_V3_2023 attendu)
try:
    from module1_urbanisme.models import MicrosoftFootprint
    fp = MicrosoftFootprint()
    if fp.source == 'Google_V3_2023':
        ok("DB-13 : MicrosoftFootprint.source default = 'Google_V3_2023' (correct — import_google_buildings)")
    else:
        warn(f"DB-13 : MicrosoftFootprint.source default = '{fp.source}' (attendu Google_V3_2023)")
except Exception as e:
    fail("DB-13 : MicrosoftFootprint source default", str(e)[:200])

# DB-14 : DetectionConstruction.latitude / longitude properties
try:
    from module1_urbanisme.models import DetectionConstruction
    d = DetectionConstruction()
    d.geometry = None
    lat = d.latitude
    lon = d.longitude
    assert lat is None and lon is None, f"lat={lat}, lon={lon} (devrait être None)"
    ok("DB-14 : latitude/longitude properties avec geometry=None → None OK")
except Exception as e:
    fail("DB-14 : latitude/longitude properties", traceback.format_exc()[-300:])

# DB-15 : StatisticsSerializer fonctionnel
try:
    from module1_urbanisme.serializers import StatisticsSerializer
    from django.utils import timezone
    data = {
        'total_zones': 10, 'zones_forbidden': 2, 'zones_conditional': 3, 'zones_buildable': 5,
        'total_detections': 7, 'detections_infraction': 1, 'detections_sous_condition': 2,
        'detections_conforme': 3, 'detections_preventive': 1,
        'total_microsoft_footprints': 100, 'last_update': timezone.now()
    }
    s = StatisticsSerializer(data)
    assert s.data['total_zones'] == 10
    ok("DB-15 : StatisticsSerializer OK")
except Exception as e:
    fail("DB-15 : StatisticsSerializer", traceback.format_exc()[-300:])

print("\n--- RÉSUMÉ DB ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
