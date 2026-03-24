"""
TEST CMD — Management commands (import dry-run, logique de parsing)
"""
import os, sys, traceback, tempfile, json

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

print("\n=== TEST CMD : Management commands ===\n")

try:
    import django
    django.setup()
except Exception as e:
    print(f"FATAL: django.setup() failed: {e}")
    sys.exit(1)

# CMD-01 : import_sentinel importable
try:
    from module1_urbanisme.management.commands.import_sentinel import Command as ImportSentinelCmd
    ok("CMD-01 : import_sentinel.Command importable")
except Exception as e:
    fail("CMD-01 : import_sentinel import", traceback.format_exc()[-300:])

# CMD-02 : import_sentinel._parse_sentinel_filename()
try:
    from module1_urbanisme.management.commands.import_sentinel import Command
    cmd = Command()
    result = cmd._parse_sentinel_filename("2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B08_(Raw).tiff")
    assert result is not None, "Résultat None pour un nom valide"
    assert result['date'] == '2024-01-29', f"Date incorrecte: {result['date']}"
    ok("CMD-02 : import_sentinel._parse_sentinel_filename() OK")
except Exception as e:
    fail("CMD-02 : _parse_sentinel_filename()", traceback.format_exc()[-300:])

# CMD-03 : import_sentinel._parse_sentinel_filename() nom invalide → None
try:
    from module1_urbanisme.management.commands.import_sentinel import Command
    cmd = Command()
    result = cmd._parse_sentinel_filename("fichier_invalide.tiff")
    assert result is None, f"Attendu None, obtenu {result}"
    ok("CMD-03 : _parse_sentinel_filename() nom invalide → None OK")
except Exception as e:
    fail("CMD-03 : _parse_sentinel_filename() invalide", traceback.format_exc()[-300:])

# CMD-04 : import_sentinel._analyze_sentinel_files() dossier new format (sous-dossiers)
try:
    from module1_urbanisme.management.commands.import_sentinel import Command
    cmd = Command()
    with tempfile.TemporaryDirectory() as tmpdir:
        date_dir = os.path.join(tmpdir, "2024-01-29")
        os.makedirs(date_dir)
        for band in ["B04", "B08", "B11"]:
            open(os.path.join(date_dir, f"{band}_2024-01-29.tif"), 'w').close()
        result = cmd._analyze_sentinel_files(tmpdir)
    assert '2024-01-29' in result, f"Date 2024-01-29 non détectée: {list(result.keys())}"
    assert 'B08' in result['2024-01-29']['bands']
    ok("CMD-04 : _analyze_sentinel_files() nouveau format OK")
except Exception as e:
    fail("CMD-04 : _analyze_sentinel_files() nouveau format", traceback.format_exc()[-300:])

# CMD-05 : import_cadastre importable
try:
    from module1_urbanisme.management.commands.import_cadastre import Command as ImportCadastre
    ok("CMD-05 : import_cadastre.Command importable")
except Exception as e:
    fail("CMD-05 : import_cadastre import", traceback.format_exc()[-300:])

# CMD-06 : import_cadastre._parse_feature()
try:
    from module1_urbanisme.management.commands.import_cadastre import Command
    cmd = Command()
    feature = {
        "id": "Z001",
        "geometry": {"type": "Polygon", "coordinates": [[[-4.01, 5.30], [-4.009, 5.30], [-4.009, 5.31], [-4.01, 5.31], [-4.01, 5.30]]]},
        "properties": {
            "zone_id": "Z001", "name": "Zone Test", "zone_type": "residential",
            "zone_status": "forbidden", "description": "Test"
        }
    }
    result = cmd._parse_feature(feature)
    assert result['zone_id'] == 'Z001'
    assert result['buildable_status'] == 'forbidden'
    ok("CMD-06 : import_cadastre._parse_feature() OK")
except Exception as e:
    fail("CMD-06 : import_cadastre._parse_feature()", traceback.format_exc()[-300:])

# CMD-07 : import_cadastre utilise BUILDABLE_STATUS_CHOICES (vérifie attribut)
try:
    from module1_urbanisme.management.commands.import_cadastre import Command
    from module1_urbanisme.models import ZoneCadastrale
    # Simuler l'appel à _print_statistics() sans BDD
    label_map = dict(ZoneCadastrale.BUILDABLE_STATUS_CHOICES)
    assert 'forbidden' in label_map
    ok("CMD-07 : import_cadastre._print_statistics() — BUILDABLE_STATUS_CHOICES OK")
except AttributeError as e:
    fail("CMD-07 : BUILDABLE_STATUS_CHOICES manquant", str(e))
except Exception as e:
    fail("CMD-07 : BUILDABLE_STATUS_CHOICES", str(e)[:200])

# CMD-08 : import_microsoft importable
try:
    from module1_urbanisme.management.commands.import_microsoft import Command as ImportMicrosoft
    ok("CMD-08 : import_microsoft.Command importable")
except Exception as e:
    fail("CMD-08 : import_microsoft import", traceback.format_exc()[-300:])

# CMD-09 : import_microsoft._is_in_bbox() logique AABB
try:
    from module1_urbanisme.management.commands.import_microsoft import Command
    cmd = Command()
    bbox = {"min_lon": -4.03, "min_lat": 5.28, "max_lon": -3.97, "max_lat": 5.32}
    feature_inside = {
        "geometry": {"type": "Polygon", "coordinates": [[
            [-4.01, 5.30], [-4.009, 5.30], [-4.009, 5.301], [-4.01, 5.301], [-4.01, 5.30]
        ]]}
    }
    feature_outside = {
        "geometry": {"type": "Polygon", "coordinates": [[
            [-5.0, 6.0], [-4.99, 6.0], [-4.99, 6.01], [-5.0, 6.01], [-5.0, 6.0]
        ]]}
    }
    assert cmd._is_in_bbox(feature_inside, bbox) == True, "Feature dans bbox non détectée"
    assert cmd._is_in_bbox(feature_outside, bbox) == False, "Feature hors bbox faussement incluse"
    ok("CMD-09 : import_microsoft._is_in_bbox() AABB OK")
except Exception as e:
    fail("CMD-09 : _is_in_bbox()", traceback.format_exc()[-300:])

# CMD-10 : import_microsoft._parse_feature() — source Microsoft_2020 ?
try:
    from module1_urbanisme.management.commands.import_microsoft import Command
    cmd = Command()
    feature = {
        "geometry": {"type": "Polygon", "coordinates": [[
            [-4.01, 5.30], [-4.009, 5.30], [-4.009, 5.301], [-4.01, 5.301], [-4.01, 5.30]
        ]]}
    }
    result = cmd._parse_feature(feature)
    if result.get('source_file') == 'Abidjan_33333010.geojsonl':
        # Source 'source' field n'est pas dans _parse_feature — vérifie la valeur default model
        from module1_urbanisme.models import MicrosoftFootprint
        fp = MicrosoftFootprint(**result)
        if fp.source == 'Google_V3_2023':
            warn("CMD-10 : import_microsoft crée des empreintes avec source='Google_V3_2023' par défaut",
                 "Des empreintes Microsoft seront identifiées comme Google_V3_2023 !")
        else:
            ok(f"CMD-10 : import_microsoft source = '{fp.source}'")
    else:
        ok("CMD-10 : import_microsoft._parse_feature() OK")
except Exception as e:
    fail("CMD-10 : import_microsoft._parse_feature()", traceback.format_exc()[-300:])

# CMD-11 : import_google_buildings importable
try:
    from module1_urbanisme.management.commands.import_google_buildings import Command as ImportGoogle
    ok("CMD-11 : import_google_buildings.Command importable")
except Exception as e:
    fail("CMD-11 : import_google_buildings import", traceback.format_exc()[-300:])

# CMD-12 : import_sentinel_api importable
try:
    from module1_urbanisme.management.commands.import_sentinel_api import Command as ImportSentinelApi
    ok("CMD-12 : import_sentinel_api.Command importable")
except Exception as e:
    fail("CMD-12 : import_sentinel_api import", traceback.format_exc()[-300:])

# CMD-13 : run_detection importable
try:
    from module1_urbanisme.management.commands.run_detection import Command as RunDetection
    ok("CMD-13 : run_detection.Command importable")
except Exception as e:
    fail("CMD-13 : run_detection import", traceback.format_exc()[-300:])

# CMD-14 : run_detection._pixel_region_to_geojson() produit GeoJSON valide
try:
    from module1_urbanisme.management.commands.run_detection import Command
    import rasterio.transform as rtransform
    from rasterio.transform import from_bounds
    cmd = Command()
    cmd.stdout = type('obj', (object,), {'write': lambda self, x: None})()
    cmd.style = type('obj', (object,), {
        'SUCCESS': lambda self, x: x, 'ERROR': lambda self, x: x,
        'WARNING': lambda self, x: x
    })()
    transform = from_bounds(-4.03, 5.28, -3.97, 5.32, 600, 400)
    region = {'centroid': (200, 300), 'size_pixels': 25}
    geojson_str = cmd._pixel_region_to_geojson(region, transform)
    geojson = json.loads(geojson_str)
    assert geojson['type'] == 'Polygon'
    coords = geojson['coordinates'][0]
    # Vérifier coordonnées dans la BBOX Treichville
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    assert all(-4.1 < lon < -3.9 for lon in lons), f"Longitude hors BBOX: {lons}"
    assert all(5.2 < lat < 5.4 for lat in lats), f"Latitude hors BBOX: {lats}"
    ok("CMD-14 : _pixel_region_to_geojson() → GeoJSON WGS84 dans BBOX Treichville OK")
except Exception as e:
    fail("CMD-14 : _pixel_region_to_geojson()", traceback.format_exc()[-300:])

# CMD-15 : run_detection.py — duplication bloc raster metadata (lignes 291-298)
try:
    import ast
    cmd_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "module1_urbanisme", "management", "commands", "run_detection.py")
    with open(cmd_path) as f:
        content = f.read()
    # Chercher la duplication du bloc raster_transform
    count = content.count('ndbi_results["raster_transform"] = src.transform')
    if count > 1:
        warn(f"CMD-15 : Bloc 'raster_transform = src.transform' dupliqué {count} fois dans run_detection.py",
             "Le bloc lignes 291-298 est identique au bloc 294-298 : duplication inutile")
    else:
        ok("CMD-15 : Pas de duplication de bloc raster_transform détectée")
except Exception as e:
    warn("CMD-15 : Vérification duplication", str(e)[:200])

print("\n--- RÉSUMÉ CMD ---")
total = len(RESULTS)
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_warn = sum(1 for r in RESULTS if r[0] == "WARN")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | WARN: {nb_warn} | FAIL: {nb_fail} | TOTAL: {total}")

if __name__ == "__main__":
    sys.exit(0 if nb_fail == 0 else 1)
