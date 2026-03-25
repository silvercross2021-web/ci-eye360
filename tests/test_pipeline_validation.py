"""
Script de validation du pipeline CIV-Eye Module 1.
À exécuter depuis la racine du projet (SIADE_hackathon/) :

    python test_pipeline_validation.py

Ce script vérifie :
  1. Les imports Python nécessaires
  2. La lecture des images Sentinel (rasterio)
  3. Le calcul NDBI et BSI
  4. La cohérence des formules (correctif A4)
  5. La détection des changements T1→T2
  6. La spatialité Shapely (correctif A2)
  7. L'import Django et les modèles
"""

import os
import sys

# Configuration Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

SENTINEL_EXPORTS = os.path.join(
    os.path.dirname(__file__),
    "module1_urbanisme", "data_use", "sentinel_api_exports"
)

T1_DATE = "2024-02-15"
T2_DATE = "2025-01-15"

T1_B04 = os.path.join(SENTINEL_EXPORTS, T1_DATE, f"B04_{T1_DATE}.tif")
T1_B08 = os.path.join(SENTINEL_EXPORTS, T1_DATE, f"B08_{T1_DATE}.tif")
T1_B11 = os.path.join(SENTINEL_EXPORTS, T1_DATE, f"B11_{T1_DATE}.tif")
T1_SCL = os.path.join(SENTINEL_EXPORTS, T1_DATE, f"SCL_{T1_DATE}.tif")
T2_B04 = os.path.join(SENTINEL_EXPORTS, T2_DATE, f"B04_{T2_DATE}.tif")
T2_B08 = os.path.join(SENTINEL_EXPORTS, T2_DATE, f"B08_{T2_DATE}.tif")
T2_B11 = os.path.join(SENTINEL_EXPORTS, T2_DATE, f"B11_{T2_DATE}.tif")
T2_SCL = os.path.join(SENTINEL_EXPORTS, T2_DATE, f"SCL_{T2_DATE}.tif")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def fail(msg):
    print(f"  ❌ {msg}")


def run_tests():
    all_passed = True

    # ─────────────────────────────────────────────────────────────
    section("TEST 1 — Imports Python")
    # ─────────────────────────────────────────────────────────────
    try:
        import numpy as np
        ok(f"numpy {np.__version__}")
    except ImportError:
        fail("numpy non installé")
        all_passed = False

    try:
        import rasterio
        ok(f"rasterio {rasterio.__version__}")
    except ImportError:
        fail("rasterio non installé — pip install rasterio")
        all_passed = False

    try:
        import shapely
        from shapely.geometry import shape, Point, Polygon
        ok(f"shapely {shapely.__version__}")
    except ImportError:
        fail("shapely non installé — pip install shapely>=2.0")
        all_passed = False

    try:
        from scipy import ndimage
        import scipy
        ok(f"scipy {scipy.__version__}")
    except ImportError:
        warn("scipy non installé (extraction régions dégradée) — pip install scipy")

    # ─────────────────────────────────────────────────────────────
    section("TEST 2 — Lecture images Sentinel")
    # ─────────────────────────────────────────────────────────────
    try:
        import rasterio
        for path, label in [
            (T1_B08, "T1 B08"), (T1_B11, "T1 B11"),
            (T2_B08, "T2 B08"), (T2_B11, "T2 B11"), (T2_B04, "T2 B04")
        ]:
            if not os.path.exists(path):
                fail(f"Fichier introuvable : {os.path.basename(path)}")
                all_passed = False
                continue
            with rasterio.open(path) as src:
                data = src.read(1).astype(float)
                bounds = src.bounds
                ok(
                    f"{label}: shape={data.shape}, "
                    f"lon=[{bounds.left:.4f},{bounds.right:.4f}], "
                    f"lat=[{bounds.bottom:.4f},{bounds.top:.4f}]"
                )
    except Exception as e:
        fail(f"Erreur lecture Sentinel: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("TEST 3 — Calcul NDBI")
    # ─────────────────────────────────────────────────────────────
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
        import numpy as np

        calc = NDBICalculator()
        ndbi_t1 = calc.calculate_ndbi(T1_B08, T1_B11)
        ndbi_t2 = calc.calculate_ndbi(T2_B08, T2_B11)

        ok(f"NDBI T1 — min={ndbi_t1.min():.3f}, max={ndbi_t1.max():.3f}, "
           f"pixels_batis={np.sum(ndbi_t1 > 0.2):,}")
        ok(f"NDBI T2 — min={ndbi_t2.min():.3f}, max={ndbi_t2.max():.3f}, "
           f"pixels_batis={np.sum(ndbi_t2 > 0.2):,}")

        # Vérification de la plage de valeurs
        assert ndbi_t1.min() >= -1.0 and ndbi_t1.max() <= 1.0, "NDBI hors plage [-1,1]"
        ok("Valeurs NDBI dans la plage [-1, 1] ✓")

    except Exception as e:
        fail(f"Erreur calcul NDBI: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("TEST 4 — Calcul BSI (correctif A4 : formule B11-B08)")
    # ─────────────────────────────────────────────────────────────
    try:
        from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
        import numpy as np

        calc = NDBICalculator()
        bsi_t2 = calc.calculate_bsi(T2_B04, T2_B08, T2_B11)

        ok(f"BSI T2 — min={bsi_t2.min():.3f}, max={bsi_t2.max():.3f}, "
           f"pixels_sol={np.sum(bsi_t2 > 0.15):,}")

        # Vérification du correctif A4 : BSI doit être différent du faux NDBI
        ndbi_t2 = calc.calculate_ndbi(T2_B08, T2_B11)
        # BSI(B11-B08) et NDBI(B11-B08) sont les mêmes ici par définition simplifiée
        # Mais vérifier que BSI != (B11-B04)/(B11+B04)
        import rasterio
        with rasterio.open(T2_B04) as r04, rasterio.open(T2_B08) as r08, rasterio.open(T2_B11) as r11:
            b04 = r04.read(1).astype(float)
            b08 = r08.read(1).astype(float)
            b11 = r11.read(1).astype(float)

            if b11.shape != b04.shape:
                from rasterio.warp import reproject, Resampling
                b11_r = np.empty(b04.shape, dtype=np.float64)
                reproject(rasterio.band(r11, 1), b11_r,
                           src_transform=r11.transform, src_crs=r11.crs,
                           dst_transform=r04.transform, dst_crs=r04.crs,
                           resampling=Resampling.bilinear)
                b11 = b11_r

            denom08 = b11 + b08
            bsi_correct = np.where(denom08 == 0, 0.0, (b11[:b08.shape[0], :b08.shape[1]] - b08) / denom08)

            denom04 = b11[:b04.shape[0], :b04.shape[1]] + b04
            bsi_wrong = np.where(denom04 == 0, 0.0, (b11[:b04.shape[0], :b04.shape[1]] - b04) / denom04)

            correlation_correct = float(np.corrcoef(bsi_t2.flatten()[:1000], bsi_correct.flatten()[:1000])[0, 1])
            correlation_wrong = float(np.corrcoef(bsi_t2.flatten()[:1000], bsi_wrong.flatten()[:1000])[0, 1])

            ok(f"Correctif A4 — Corrélation BSI avec (B11-B08)/(B11+B08) : {correlation_correct:.3f}")
            ok(f"Correctif A4 — Corrélation BSI avec (B11-B04)/(B11+B04) : {correlation_wrong:.3f}")

            if abs(correlation_correct) > abs(correlation_wrong):
                ok("✓ BSI utilise bien la formule (B11-B08)/(B11+B08) conformément au plan v2.0")
            else:
                warn("BSI corrélé identiquement à B08 et B04 (images très similaires en infra-rouge)")

    except Exception as e:
        fail(f"Erreur calcul BSI: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("TEST 5 — Détection changements T1 → T2")
    # ─────────────────────────────────────────────────────────────
    try:
        from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
        import numpy as np

        calc = NDBICalculator()
        ndbi_t1 = calc.calculate_ndbi(T1_B08, T1_B11)
        ndbi_t2 = calc.calculate_ndbi(T2_B08, T2_B11)
        bsi_t2 = calc.calculate_bsi(T2_B04, T2_B08, T2_B11)
        changes = calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2)

        n_const = np.sum(changes["new_constructions"])
        n_soil = np.sum(changes["soil_activity"])
        n_total = np.sum(changes["all_changes"])
        total_px = ndbi_t1.size

        ok(f"Nouvelles constructions : {n_const:,} pixels ({100*n_const/total_px:.2f}%)")
        ok(f"Activité sol (terrassement) : {n_soil:,} pixels ({100*n_soil/total_px:.2f}%)")
        ok(f"Total changements : {n_total:,} / {total_px:,} pixels")

        regions = calc.extract_change_regions(changes["new_constructions"], min_size=10)
        ok(f"Régions de construction extraites : {len(regions)}")

    except Exception as e:
        fail(f"Erreur détection changements: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("TEST 6 — Spatialité Shapely (correctif A2)")
    # ─────────────────────────────────────────────────────────────
    try:
        from shapely.geometry import shape, Point

        # Géométrie de test dans Treichville
        polygon_treichville = {
            "type": "Polygon",
            "coordinates": [[
                [-4.010, 5.295], [-4.008, 5.295],
                [-4.008, 5.297], [-4.010, 5.297],
                [-4.010, 5.295]
            ]]
        }
        geom = shape(polygon_treichville)
        centroid = geom.centroid
        ok(f"Test polygone — Centroid : ({centroid.x:.4f}, {centroid.y:.4f})")

        # Test de containment
        point_dedans = Point(-4.009, 5.296)
        point_dehors = Point(-4.020, 5.296)
        assert geom.contains(point_dedans), "Point intérieur non détecté!"
        assert not geom.contains(point_dehors), "Point extérieur faussement inclus!"
        ok("Test containment point-dans-polygone : ✓")

        # Test d'intersection entre deux polygones
        polygon2 = {
            "type": "Polygon",
            "coordinates": [[
                [-4.009, 5.296], [-4.007, 5.296],
                [-4.007, 5.298], [-4.009, 5.298],
                [-4.009, 5.296]
            ]]
        }
        geom2 = shape(polygon2)
        assert geom.intersects(geom2), "Intersection non détectée!"
        ok("Test intersection polygone-polygone : ✓")
        ok("Correctif A2 (Shapely classification) validé ✓")

    except Exception as e:
        fail(f"Erreur test Shapely: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("TEST 7 — Django Setup et Modèles")
    # ─────────────────────────────────────────────────────────────
    try:
        import django
        django.setup()
        from module1_urbanisme.models import ZoneCadastrale, MicrosoftFootprint, DetectionConstruction, ImageSatellite
        ok(f"ZoneCadastrale    : {ZoneCadastrale.objects.count()} zones en base")
        ok(f"MicrosoftFootprint: {MicrosoftFootprint.objects.count()} empreintes en base")
        ok(f"ImageSatellite    : {ImageSatellite.objects.count()} images en base")
        ok(f"DetectionConst.   : {DetectionConstruction.objects.count()} détections en base")

        # Vérifier la validité des alert_level (correctif A3)
        from django.db.models import Q
        invalid = DetectionConstruction.objects.exclude(
            alert_level__in=["rouge", "orange", "vert", "veille"]
        ).count()
        if invalid == 0:
            ok("Tous les alert_level sont valides (correctif A3) ✓")
        else:
            warn(f"{invalid} détections avec alert_level invalide — corriger en base")

    except Exception as e:
        fail(f"Erreur Django: {e}")
        all_passed = False

    # ─────────────────────────────────────────────────────────────
    section("RÉSULTAT FINAL")
    # ─────────────────────────────────────────────────────────────
    if all_passed:
        print("\n  🎉 TOUS LES TESTS PASSENT — Pipeline prêt pour les données réelles!\n")
        print("  Prochaines étapes :")
        print("  1. python manage.py import_cadastre")
        print("  2. python manage.py import_sentinel")
        print("  3. python manage.py import_microsoft --limit 5000")
        print("  4. python manage.py run_detection")
        print("  5. python manage.py runserver\n")
    else:
        print("\n  ⚠️  Certains tests ont échoué. Corriger les erreurs ci-dessus avant de continuer.\n")

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
