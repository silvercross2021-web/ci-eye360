"""
Management command pour importer les Microsoft Building Footprints.

CORRECTIFS APPLIQUÉS :
  - A7  : Filtrage BBOX sur l'enveloppe complète du polygone (plus du premier point seul)
  - B1  : bulk_create par chunks (plus de INSERT un par un — vastement plus rapide)
"""

import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from module1_urbanisme.models import MicrosoftFootprint


# BBOX Treichville (SRID 4326)
DEFAULT_BBOX = "-4.03001,5.28501,-3.97301,5.32053"
DEFAULT_FILE = "module1_urbanisme/data_use/Abidjan_33333010.geojsonl"
CHUNK_SIZE = 500   # nombre d'objets par bulk_create


class Command(BaseCommand):
    help = "Importe les empreintes de bâtiments Microsoft depuis le fichier GeoJSON Lines"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=str, default=DEFAULT_FILE,
            help="Chemin vers le fichier GeoJSON Lines Microsoft",
        )
        parser.add_argument(
            "--bbox", type=str, default=DEFAULT_BBOX,
            help="Bounding box Treichville (minLon,minLat,maxLon,maxLat)",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Limite de features à importer (0 = pas de limite, pour import complet)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les statistiques sans importer",
        )

    # ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        file_path = options["file"]
        bbox = self._parse_bbox(options["bbox"])
        limit = options["limit"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Import Microsoft Footprints depuis : {file_path}")
        self.stdout.write(
            f"BBOX Treichville : lon [{bbox['min_lon']}, {bbox['max_lon']}] "
            f"lat [{bbox['min_lat']}, {bbox['max_lat']}]"
        )
        self.stdout.write(f"Limite : {'illimitée' if limit == 0 else limit}")
        if dry_run:
            self.stdout.write("⚠️  MODE DRY-RUN\n")

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable : {file_path}"))
            return

        imported_count = 0
        skipped_count = 0
        error_count = 0
        chunk: list[MicrosoftFootprint] = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    # Respect de la limite (0 = illimitée)
                    if limit > 0 and i >= limit:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        feature = json.loads(line)

                        # CORRECTIF A7 : filtrage sur l'enveloppe complète du polygone
                        if not self._is_in_bbox(feature, bbox):
                            skipped_count += 1
                            continue

                        if dry_run:
                            imported_count += 1
                        else:
                            footprint_data = self._parse_feature(feature)
                            chunk.append(MicrosoftFootprint(**footprint_data))
                            imported_count += 1

                            # CORRECTIF B1 : bulk_create par chunks
                            if len(chunk) >= CHUNK_SIZE:
                                self._flush_chunk(chunk)
                                chunk = []

                    except json.JSONDecodeError:
                        error_count += 1
                    except Exception as e:
                        error_count += 1
                        if error_count <= 5:  # Limiter la verbosité
                            self.stdout.write(f"  Erreur ligne {i} : {e}")

                    if (i + 1) % 5000 == 0:
                        self.stdout.write(
                            f"  Traité {i+1:,} lignes | In bbox: {imported_count:,} | "
                            f"Hors bbox: {skipped_count:,}"
                        )

            # Dernier chunk
            if chunk and not dry_run:
                self._flush_chunk(chunk)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de l'import : {str(e)}"))
            return

        self.stdout.write(self.style.SUCCESS("\n=== RÉSUMÉ IMPORT ==="))
        self.stdout.write(f"Empreintes importées       : {imported_count:,}")
        self.stdout.write(f"Empreintes hors bbox       : {skipped_count:,}")
        self.stdout.write(f"Erreurs de parsing         : {error_count:,}")

        if not dry_run:
            total = MicrosoftFootprint.objects.count()
            self.stdout.write(f"Total en base (Treichville): {total:,}")

    # ─────────────────────────────────────────────────────────────────────
    def _flush_chunk(self, chunk: list):
        """Insère un chunk d'empreintes en base via bulk_create."""
        with transaction.atomic():
            MicrosoftFootprint.objects.bulk_create(chunk, batch_size=CHUNK_SIZE)

    def _parse_bbox(self, bbox_str: str) -> dict:
        """Parse la chaîne 'minLon,minLat,maxLon,maxLat'."""
        parts = [float(x) for x in bbox_str.split(",")]
        return {
            "min_lon": parts[0], "min_lat": parts[1],
            "max_lon": parts[2], "max_lat": parts[3],
        }

    def _is_in_bbox(self, feature: dict, bbox: dict) -> bool:
        """
        CORRECTIF A7 : Vérifie si le polygone intersecte la bounding box
        en testant l'enveloppe COMPLÈTE du polygone (plus d'un seul point).
        Un bâtiment à cheval sur la limite de Treichville est correctement inclus.
        """
        geometry = feature.get("geometry", {})
        if not geometry or geometry.get("type") != "Polygon":
            return False

        coordinates = geometry.get("coordinates", [])
        if not coordinates or not coordinates[0]:
            return False

        all_coords = coordinates[0]
        try:
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
        except (IndexError, TypeError):
            return False

        poly_min_lon, poly_max_lon = min(lons), max(lons)
        poly_min_lat, poly_max_lat = min(lats), max(lats)

        # Chevauchement AABB (même partiel)
        return not (
            poly_max_lon < bbox["min_lon"]
            or poly_min_lon > bbox["max_lon"]
            or poly_max_lat < bbox["min_lat"]
            or poly_min_lat > bbox["max_lat"]
        )

    def _parse_feature(self, feature: dict) -> dict:
        """Extrait les données d'une feature GeoJSON pour créer un MicrosoftFootprint."""
        geometry = feature.get("geometry")
        return {
            "geometry_geojson": json.dumps(geometry),
            "source_file": "Abidjan_33333010.geojsonl",
            "date_reference": "~2023-2024",
        }
