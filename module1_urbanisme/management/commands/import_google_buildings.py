"""
Management command pour importer les Google Open Buildings V3 via Google Earth Engine.

Remplace l'import Microsoft Building Footprints (données 2020, obsolètes).
Source : GOOGLE/Research/open-buildings/v3/polygons (mai 2023, 50cm/pixel, CC-BY 4.0)

3 niveaux de confiance Google :
  - Rouge  : 0.65 → 0.70 (possible)
  - Jaune  : 0.70 → 0.75 (probable)
  - Vert   : >= 0.75     (certain)

Prérequis :
  - GEE_PROJECT_ID dans .env
  - earthengine authenticate (une seule fois dans le terminal)
"""

import json
import logging
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from module1_urbanisme.models import MicrosoftFootprint

logger = logging.getLogger(__name__)

# BBOX Treichville, Abidjan (SRID 4326)
TREICHVILLE_BBOX = [-4.03001, 5.28501, -3.97301, 5.32053]
CHUNK_SIZE = 500
MIN_CONFIDENCE = 0.65  # Minimum Google Open Buildings confidence


class Command(BaseCommand):
    help = "Importe les empreintes Google Open Buildings V3 via GEE pour Treichville"

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-confidence", type=float, default=MIN_CONFIDENCE,
            help=f"Score minimum de confiance Google (défaut: {MIN_CONFIDENCE})",
        )
        parser.add_argument(
            "--bbox", type=str, default=",".join(str(x) for x in TREICHVILLE_BBOX),
            help="Bounding box (minLon,minLat,maxLon,maxLat)",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Supprimer les empreintes existantes avant import",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les statistiques sans importer",
        )
        parser.add_argument(
            "--from-geojson", type=str, default="",
            help="Importer depuis un fichier GeoJSON local au lieu de GEE (pour tests offline)",
        )

    def handle(self, *args, **options):
        min_confidence = options["min_confidence"]
        bbox = [float(x) for x in options["bbox"].split(",")]
        clear = options["clear"]
        dry_run = options["dry_run"]
        from_geojson = options["from_geojson"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== Import Google Open Buildings V3 ==="
        ))
        self.stdout.write(f"  BBOX : {bbox}")
        self.stdout.write(f"  Confiance minimum : {min_confidence}")

        if clear and not dry_run:
            deleted_count = MicrosoftFootprint.objects.all().delete()[0]
            self.stdout.write(f"  Empreintes supprimées : {deleted_count}")

        if from_geojson:
            features = self._load_from_geojson(from_geojson, min_confidence)
        else:
            features = self._load_from_gee(bbox, min_confidence)

        if features is None:
            return

        self.stdout.write(f"  Bâtiments trouvés : {len(features)}")

        if dry_run:
            self._print_stats(features)
            return

        self._import_features(features)

        total = MicrosoftFootprint.objects.filter(source='Google_V3_2023').count()
        self.stdout.write(self.style.SUCCESS(
            f"\n  Total Google V3 en base : {total:,}"
        ))

    def _load_from_gee(self, bbox, min_confidence):
        """Télécharge les bâtiments Google Open Buildings V3 via GEE."""
        try:
            import ee
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "earthengine-api non installé. pip install earthengine-api"
            ))
            return None

        project_id = os.getenv("GEE_PROJECT_ID", "")
        if not project_id:
            self.stdout.write(self.style.ERROR(
                "GEE_PROJECT_ID manquant dans .env"
            ))
            return None

        try:
            ee.Initialize(project=project_id)
            self.stdout.write("  GEE connecté avec succès")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur GEE : {e}"))
            return None

        # Définir la zone d'intérêt
        roi = ee.Geometry.Rectangle(bbox)

        # Charger Google Open Buildings V3
        buildings = (
            ee.FeatureCollection("GOOGLE/Research/open-buildings/v3/polygons")
            .filterBounds(roi)
            .filter(ee.Filter.gte("confidence", min_confidence))
        )

        count = buildings.size().getInfo()
        self.stdout.write(f"  Bâtiments GEE (confiance >= {min_confidence}) : {count}")

        if count == 0:
            self.stdout.write(self.style.WARNING("Aucun bâtiment trouvé"))
            return []

        if count > 50000:
            self.stdout.write(self.style.WARNING(
                f"  Trop de bâtiments ({count}). Import par lots..."
            ))

        # Récupérer les features par lots
        features = []
        batch_size = 5000
        building_list = buildings.toList(count)

        for offset in range(0, count, batch_size):
            end = min(offset + batch_size, count)
            self.stdout.write(f"  Téléchargement {offset+1}-{end}/{count}...")
            batch = ee.FeatureCollection(building_list.slice(offset, end))
            batch_geojson = batch.getInfo()

            for f in batch_geojson.get("features", []):
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                features.append({
                    "geometry": geom,
                    "confidence": props.get("confidence", 0.0),
                    "area_in_meters": props.get("area_in_meters", 0.0),
                    "full_plus_code": props.get("full_plus_code", ""),
                })

        return features

    def _load_from_geojson(self, filepath, min_confidence):
        """Charge depuis un fichier GeoJSON local (mode offline/test)."""
        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable : {filepath}"))
            return None

        features = []
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            conf = props.get("confidence", 0.0)
            if conf >= min_confidence:
                features.append({
                    "geometry": feat.get("geometry", {}),
                    "confidence": conf,
                    "area_in_meters": props.get("area_in_meters", 0.0),
                    "full_plus_code": props.get("full_plus_code", ""),
                })

        return features

    def _import_features(self, features):
        """Importe les features en base par chunks."""
        chunk = []
        imported = 0

        for feat in features:
            try:
                geom_json = json.dumps(feat["geometry"])
                geos_geom = GEOSGeometry(geom_json)

                chunk.append(MicrosoftFootprint(
                    geometry=geos_geom,
                    source_file="google_open_buildings_v3",
                    source="Google_V3_2023",
                    date_reference="2023-05",
                    confidence_score=feat.get("confidence"),
                ))
                imported += 1

                if len(chunk) >= CHUNK_SIZE:
                    self._flush_chunk(chunk)
                    chunk = []
                    self.stdout.write(f"    Importé : {imported:,}")

            except Exception as e:
                logger.warning(f"Erreur import bâtiment : {e}")
                continue

        if chunk:
            self._flush_chunk(chunk)

        self.stdout.write(self.style.SUCCESS(f"  Importé : {imported:,} bâtiments"))

    def _flush_chunk(self, chunk):
        """Insère un chunk en base via bulk_create."""
        with transaction.atomic():
            MicrosoftFootprint.objects.bulk_create(chunk, batch_size=CHUNK_SIZE)

    def _print_stats(self, features):
        """Affiche les statistiques de confiance (mode dry-run)."""
        if not features:
            return

        confidences = [f["confidence"] for f in features]
        rouge = sum(1 for c in confidences if 0.65 <= c < 0.70)
        jaune = sum(1 for c in confidences if 0.70 <= c < 0.75)
        vert = sum(1 for c in confidences if c >= 0.75)

        self.stdout.write("\n  Répartition par niveau de confiance :")
        self.stdout.write(f"    Rouge  (0.65-0.70) : {rouge:,}")
        self.stdout.write(f"    Jaune  (0.70-0.75) : {jaune:,}")
        self.stdout.write(f"    Vert   (>= 0.75)   : {vert:,}")
        self.stdout.write(f"    TOTAL              : {len(features):,}")
