"""
Exporte les MicrosoftFootprint en base vers un fichier GeoJSON de sauvegarde.
Usage : python manage.py export_footprints
        python manage.py export_footprints --output chemin/fichier.geojson
"""

import json
import os
from django.core.management.base import BaseCommand
from module1_urbanisme.models import MicrosoftFootprint


DEFAULT_OUTPUT = "module1_urbanisme/data_use/backup_footprints_microsoft.geojson"


class Command(BaseCommand):
    help = "Exporte tous les MicrosoftFootprint en base vers un fichier GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", type=str, default=DEFAULT_OUTPUT,
            help=f"Chemin du fichier GeoJSON de sortie (défaut : {DEFAULT_OUTPUT})",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        total = MicrosoftFootprint.objects.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("Aucun footprint en base. Rien à exporter."))
            return

        self.stdout.write(f"Export de {total:,} footprints vers : {output_path}")

        features = []
        qs = MicrosoftFootprint.objects.all().iterator(chunk_size=1000)

        for i, fp in enumerate(qs, 1):
            try:
                geom_json = json.loads(fp.geometry.json)
                features.append({
                    "type": "Feature",
                    "geometry": geom_json,
                    "properties": {
                        "id": fp.pk,
                        "source": fp.source,
                        "source_file": fp.source_file,
                        "date_reference": fp.date_reference,
                        "confidence_score": float(fp.confidence_score) if fp.confidence_score else None,
                    }
                })
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Erreur footprint #{fp.pk} : {e}"))
                continue

            if i % 5000 == 0:
                self.stdout.write(f"  Traité : {i:,}/{total:,}...")

        geojson = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features,
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_mb = os.path.getsize(output_path) / 1_048_576
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Export terminé : {len(features):,} features → {output_path} ({size_mb:.1f} Mo)"
        ))
        self.stdout.write(
            f"   Pour réimporter : python manage.py import_google_buildings --from-geojson {output_path}"
        )
