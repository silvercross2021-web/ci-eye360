"""
Management command pour importer le cadastre V10 de Treichville.

CORRECTIFS APPLIQUÉS :
  - A9 : Remplacement de 'models.Count' par 'Count' importé depuis django.db.models
         (l'ancien code causait un NameError car 'models' n'était pas importé)
"""

import json
import os

from django.core.management.base import BaseCommand
from django.db.models import Count   # ← CORRECTIF A9 (was: models.Count → NameError)

from module1_urbanisme.models import ZoneCadastrale

DEFAULT_FILE = "module1_urbanisme/data_use/cadastre_treichville_v10 (1).geojson"


class Command(BaseCommand):
    help = "Importe les zones cadastrales depuis le fichier cadastre_treichville_v10.geojson"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=str, default=DEFAULT_FILE,
            help="Chemin vers le fichier GeoJSON du cadastre",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les zones à importer sans créer en base",
        )

    # ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Import du cadastre depuis : {file_path}")

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable : {file_path}"))
            return

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            features = data.get("features", [])
            metadata = data.get("_metadata", {})

            self.stdout.write(
                f"Métadonnées : version={metadata.get('version', 'N/A')} — "
                f"{metadata.get('zones', 0)} zones déclarées"
            )
            self.stdout.write(f"Features GeoJSON détectées : {len(features)}")

            imported_count = 0
            skipped_count = 0
            errors = []

            for feature in features:
                try:
                    zone_data = self._parse_feature(feature)

                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] {zone_data['zone_id']} — "
                            f"{zone_data['name']} ({zone_data['buildable_status']})"
                        )
                        imported_count += 1
                        continue

                    # Mise à jour si déjà existante, création sinon
                    if ZoneCadastrale.objects.filter(zone_id=zone_data["zone_id"]).exists():
                        zone = ZoneCadastrale.objects.get(zone_id=zone_data["zone_id"])
                        self._update_zone(zone, zone_data)
                        self.stdout.write(f"Mis à jour : {zone}")
                    else:
                        zone = ZoneCadastrale.objects.create(**zone_data)
                        self.stdout.write(self.style.SUCCESS(f"Créé : {zone}"))

                    imported_count += 1

                except Exception as e:
                    errors.append(
                        f"Erreur feature {feature.get('id', feature.get('properties', {}).get('zone_id', '?'))}: {e}"
                    )
                    skipped_count += 1

            # Résumé
            self.stdout.write(self.style.SUCCESS("\n=== RÉSUMÉ IMPORT ==="))
            self.stdout.write(f"Zones importées/mises à jour : {imported_count}")
            self.stdout.write(f"Zones ignorées (erreurs)      : {skipped_count}")

            if errors:
                self.stdout.write(self.style.ERROR(f"\nErreurs ({len(errors)}) :"))
                for err in errors[:10]:
                    self.stdout.write(f"  - {err}")
                if len(errors) > 10:
                    self.stdout.write(f"  ... et {len(errors) - 10} autres erreurs")

            if not dry_run:
                self._print_statistics()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de l'import : {str(e)}"))

    # ─────────────────────────────────────────────────────────────────────
    def _parse_feature(self, feature: dict) -> dict:
        """Extrait les données d'une feature GeoJSON cadastrale."""
        properties = feature.get("properties", {})
        geometry = feature.get("geometry")

        # Mapping zone_status → buildable_status
        zone_status = properties.get("zone_status", "buildable")
        if zone_status == "forbidden":
            buildable_status = "forbidden"
        elif zone_status == "conditional":
            buildable_status = "conditional"
        else:
            buildable_status = "buildable"

        return {
            "zone_id": properties.get("zone_id") or feature.get("id"),
            "name": properties.get("name", "Zone inconnue"),
            "zone_type": properties.get("zone_type", "residential"),
            "buildable_status": buildable_status,
            "geometry_geojson": json.dumps(geometry),
            "metadata": {
                "description": properties.get("description", ""),
                "bbox": feature.get("bbox"),
                "zone_status_original": zone_status,
                "surface_ha": properties.get("surface_ha"),
            },
        }

    def _update_zone(self, zone: ZoneCadastrale, zone_data: dict):
        """Met à jour une zone cadastrale existante."""
        zone.name = zone_data["name"]
        zone.zone_type = zone_data["zone_type"]
        zone.buildable_status = zone_data["buildable_status"]
        zone.geometry_geojson = zone_data["geometry_geojson"]
        zone.metadata = zone_data["metadata"]
        zone.save()

    def _print_statistics(self):
        """Affiche les statistiques post-import."""
        self.stdout.write(self.style.SUCCESS("\n=== STATISTIQUES CADASTRALES ==="))

        # CORRECTIF A9 : utilise Count() importé, pas models.Count()
        stats = ZoneCadastrale.objects.values("buildable_status").annotate(count=Count("id"))
        label_map = dict(ZoneCadastrale.BUILDABLE_STATUS_CHOICES)

        for stat in stats:
            label = label_map.get(stat["buildable_status"], stat["buildable_status"])
            self.stdout.write(f"  {label:<35} : {stat['count']}")

        total = ZoneCadastrale.objects.count()
        self.stdout.write(f"  {'TOTAL':<35} : {total}")
