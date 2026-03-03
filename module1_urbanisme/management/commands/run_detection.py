"""
Management command pour exécuter le pipeline complet de détection NDBI + vérification 4 couches.

CORRECTIFS APPLIQUÉS:
  - A6 : Les géométries sont converties de coordonnées pixel → WGS84 (longitude/latitude)
         via le transform affine du raster Sentinel-2.
         L'ancienne implémentation créait des polygones en coordonnées pixel invalides.
"""

import json
import logging
from datetime import date

import numpy as np
import rasterio
import rasterio.transform as rtransform

from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.utils import timezone

from module1_urbanisme.models import ImageSatellite, DetectionConstruction
from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
from module1_urbanisme.pipeline.verification_4_couches import DetectionPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Résolution Sentinel-2 B08 en degrés (≈10m à la latitude d'Abidjan ~5.3°N)
# 10m / (111 000 m/deg) ≈ 0.00009 degrés
PIXEL_SIZE_DEGREES = 0.00009


class Command(BaseCommand):
    help = "Exécute le pipeline complet de détection NDBI + vérification 4 couches"

    def add_arguments(self, parser):
        parser.add_argument("--date-t1", type=str, help="Date image T1 (YYYY-MM-DD)")
        parser.add_argument("--date-t2", type=str, help="Date image T2 (YYYY-MM-DD)")
        parser.add_argument(
            "--threshold-built", type=float, default=0.2,
            help="Seuil NDBI pour surfaces bâties (défaut: 0.2)"
        )
        parser.add_argument(
            "--threshold-soil", type=float, default=0.15,
            help="Seuil BSI pour sol nu (défaut: 0.15)"
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les résultats sans écrire en base"
        )
        parser.add_argument(
            "--min-region-size", type=int, default=10,
            help="Taille minimale en pixels pour une région (défaut: 10)"
        )

    def handle(self, *args, **options):
        date_t1 = options.get("date_t1")
        date_t2 = options.get("date_t2")
        threshold_built = options["threshold_built"]
        threshold_soil = options["threshold_soil"]
        dry_run = options["dry_run"]
        min_region_size = options["min_region_size"]

        self.stdout.write("🚀 LANCEMENT PIPELINE DE DÉTECTION CIV-EYE MODULE 1")
        self.stdout.write(f"📅 Période    : {date_t1 or 'auto'} → {date_t2 or 'auto'}")
        self.stdout.write(f"🎯 Seuils     : NDBI bâti={threshold_built}, BSI sol={threshold_soil}")
        self.stdout.write(f"🔬 Min pixels : {min_region_size}")
        if dry_run:
            self.stdout.write("⚠️  MODE DRY-RUN — aucune écriture en base\n")

        try:
            # ── Étape 1 : Récupération des images ────────────────────────
            image_t1, image_t2 = self.get_sentinel_images(date_t1, date_t2)

            # ── Étape 2 : Calcul NDBI + BSI + Détection changements ──────
            self.stdout.write("\n📊 Étape 1 : Calcul NDBI T1 / T2 / BSI T2...")
            ndbi_results = self.calculate_ndbi_pipeline(
                image_t1, image_t2, threshold_built, threshold_soil
            )

            # ── Étape 3 : Extraction des régions ─────────────────────────
            self.stdout.write("🔍 Étape 2 : Extraction des régions de changement...")
            change_regions = self.extract_change_regions(
                ndbi_results, min_region_size
            )
            self.stdout.write(
                f"   → {sum(1 for r in change_regions if r['change_type']=='new_construction')} "
                f"nouvelles constructions + "
                f"{sum(1 for r in change_regions if r['change_type']=='soil_activity')} terrassements"
            )

            # ── Étape 4 : Vérification 4 couches ─────────────────────────
            self.stdout.write("✅ Étape 3 : Vérification 4 couches + classification...")
            if not dry_run:
                detections = self.process_4couches_verification(change_regions, image_t2)
                self.stdout.write(
                    self.style.SUCCESS(f"   → {len(detections)} détections créées en base")
                )
            else:
                self.stdout.write(
                    f"   [DRY-RUN] Créerait {len(change_regions)} détections potentielles"
                )

            # ── Étape 5 : Statistiques ────────────────────────────────────
            self.print_detection_statistics()
            self.stdout.write(self.style.SUCCESS("\n🎉 PIPELINE TERMINÉ AVEC SUCCÈS"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERREUR PIPELINE : {str(e)}"))
            logger.error("Erreur pipeline", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────
    def get_sentinel_images(self, date_t1=None, date_t2=None):
        """Récupère les images Sentinel T1 et T2 depuis la BDD."""
        if not date_t1 or not date_t2:
            images = ImageSatellite.objects.order_by("date_acquisition")
            if images.count() < 2:
                raise ValueError(
                    "Moins de 2 images en base. "
                    "Exécuter d'abord : python manage.py import_sentinel"
                )
            image_t1 = images.first()
            image_t2 = images.last()
        else:
            image_t1 = ImageSatellite.objects.get(date_acquisition=date.fromisoformat(date_t1))
            image_t2 = ImageSatellite.objects.get(date_acquisition=date.fromisoformat(date_t2))

        self.stdout.write(
            f"📷 Images sélectionnées : T1={image_t1.date_acquisition}, T2={image_t2.date_acquisition}"
        )
        return image_t1, image_t2

    # ─────────────────────────────────────────────────────────────────────
    def calculate_ndbi_pipeline(self, image_t1, image_t2, threshold_built, threshold_soil):
        """Calcule les NDBI T1/T2, le BSI T2, et détecte les changements."""
        calc = NDBICalculator()
        calc.threshold_built = threshold_built
        calc.threshold_soil = threshold_soil

        bands_t1 = image_t1.bands
        bands_t2 = image_t2.bands

        # Vérification des bandes requises
        for band in ("B08", "B11"):
            if band not in bands_t1:
                raise ValueError(f"Bande {band} manquante pour T1 ({image_t1.date_acquisition})")
            if band not in bands_t2:
                raise ValueError(f"Bande {band} manquante pour T2 ({image_t2.date_acquisition})")

        self.stdout.write("   Calcul NDBI T1...")
        ndbi_t1 = calc.calculate_ndbi(bands_t1["B08"], bands_t1["B11"])

        self.stdout.write("   Calcul NDBI T2...")
        ndbi_t2 = calc.calculate_ndbi(bands_t2["B08"], bands_t2["B11"])

        bsi_t2 = None
        if "B04" in bands_t2 and "B08" in bands_t2 and "B11" in bands_t2:
            self.stdout.write("   Calcul BSI T2...")
            bsi_t2 = calc.calculate_bsi(bands_t2["B04"], bands_t2["B08"], bands_t2["B11"])

        self.stdout.write("   Détection changements...")
        change_results = calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2)

        # Récupérer le transform du raster B08 de T2 pour la conversion pixel→geo
        with rasterio.open(bands_t2["B08"]) as src:
            raster_transform = src.transform

        return {
            "ndbi_t1": ndbi_t1,
            "ndbi_t2": ndbi_t2,
            "bsi_t2": bsi_t2,
            "changes": change_results,
            "raster_transform": raster_transform,   # ← NOUVEAU : pour pixel→WGS84
        }

    # ─────────────────────────────────────────────────────────────────────
    def extract_change_regions(self, ndbi_results, min_region_size):
        """Extrait les régions et enrichit chaque région avec géométrie WGS84 et valeurs NDBI."""
        calc = NDBICalculator()
        raster_transform = ndbi_results["raster_transform"]
        ndbi_t1 = ndbi_results["ndbi_t1"]
        ndbi_t2 = ndbi_results["ndbi_t2"]
        bsi_t2 = ndbi_results.get("bsi_t2")

        all_regions = []

        # Régions nouvelles constructions
        construction_regions = calc.extract_change_regions(
            ndbi_results["changes"]["new_constructions"], min_region_size
        )
        for region in construction_regions:
            region["change_type"] = "new_construction"
            region["geometry_geojson"] = self._pixel_region_to_geojson(region, raster_transform)
            # Valeurs NDBI moyennes sur la région
            row, col = region["centroid"]
            region["ndbi_t1"] = float(ndbi_t1[row, col])
            region["ndbi_t2"] = float(ndbi_t2[row, col])
            region["bsi"] = float(bsi_t2[row, col]) if bsi_t2 is not None else None
            all_regions.append(region)

        # Régions terrassement
        soil_regions = calc.extract_change_regions(
            ndbi_results["changes"]["soil_activity"], min_region_size
        )
        for region in soil_regions:
            region["change_type"] = "soil_activity"
            region["geometry_geojson"] = self._pixel_region_to_geojson(region, raster_transform)
            row, col = region["centroid"]
            region["ndbi_t1"] = float(ndbi_t1[row, col])
            region["ndbi_t2"] = float(ndbi_t2[row, col])
            region["bsi"] = float(bsi_t2[row, col]) if bsi_t2 is not None else None
            all_regions.append(region)

        return all_regions

    # ─────────────────────────────────────────────────────────────────────
    def _pixel_region_to_geojson(self, region: dict, raster_transform) -> str:
        """
        Convertit une région raster (coordonnées pixels) en polygone GeoJSON WGS84.

        CORRECTIF A6 : l'ancienne implémentation utilisait les coordonnées pixels
        (lignes/colonnes) comme si c'étaient des longitudes/latitudes,
        ce qui produisait des géométries complètement hors de Treichville.

        On utilise maintenant le transform affine rasterio pour obtenir les vraies
        coordonnées géographiques (lon/lat en WGS84).

        Args:
            region:           Dict contenant 'centroid' (row, col) et 'size_pixels'
            raster_transform: Transform affine rasterio du raster source

        Returns:
            GeoJSON Polygon string avec coordonnées lon/lat.
        """
        centroid_row, centroid_col = region["centroid"]
        size_pixels = max(region.get("size_pixels", 10), 1)

        # Conversion centroid pixel → lon/lat
        lon_center, lat_center = rtransform.xy(
            raster_transform, centroid_row, centroid_col
        )

        # Estimation de la taille du polygone en degrés
        # sqrt(N pixels) × résolution pixel en degrés ÷ 2 → demi-côté
        half_side = (np.sqrt(size_pixels) * PIXEL_SIZE_DEGREES) / 2
        half_side = max(half_side, PIXEL_SIZE_DEGREES)  # minimum 1 pixel de côté

        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [lon_center - half_side, lat_center - half_side],
                [lon_center + half_side, lat_center - half_side],
                [lon_center + half_side, lat_center + half_side],
                [lon_center - half_side, lat_center + half_side],
                [lon_center - half_side, lat_center - half_side],  # fermeture
            ]],
        }
        return json.dumps(geometry)

    # ─────────────────────────────────────────────────────────────────────
    def process_4couches_verification(self, regions, image_t2):
        """Applique la vérification 4 couches et écrit les détections en BDD."""
        pipeline = DetectionPipeline()
        image_metadata = {
            "date_t2": str(image_t2.date_acquisition),
            "bands_t2": image_t2.bands,
        }
        with transaction.atomic():
            detections = pipeline.process_detection_regions(regions, image_metadata)

        image_t2.processed = True
        image_t2.save()
        return detections

    # ─────────────────────────────────────────────────────────────────────
    def print_detection_statistics(self):
        """Affiche les statistiques des détections dans la BDD."""
        self.stdout.write(self.style.SUCCESS("\n📊 STATISTIQUES FINALES"))

        total = DetectionConstruction.objects.count()
        if total == 0:
            self.stdout.write("   (Aucune détection en base)")
            return

        stats = (
            DetectionConstruction.objects.values("status")
            .annotate(count=models.Count("id"))
            .order_by("status")
        )
        self.stdout.write("   Par statut :")
        for s in stats:
            self.stdout.write(f"     {s['status']:<35} : {s['count']}")

        alert_stats = (
            DetectionConstruction.objects.values("alert_level")
            .annotate(count=models.Count("id"))
            .order_by("alert_level")
        )
        emoji_map = {"rouge": "🔴", "orange": "🟠", "vert": "🟢", "veille": "🔵"}
        self.stdout.write("   Par niveau d'alerte :")
        for a in alert_stats:
            emoji = emoji_map.get(a["alert_level"], "⚪")
            self.stdout.write(f"     {emoji} {a['alert_level']:<10} : {a['count']}")

        self.stdout.write(f"   TOTAL : {total} détections")
