"""
Management command pour importer les images Sentinel-2.

CORRECTIFS APPLIQUÉS :
  - A8 : Les chemins des bandes sont stockés en chemin absolu (via settings.BASE_DIR)
         afin d'éviter des FileNotFoundError selon le répertoire de lancement.
"""

import os
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from module1_urbanisme.models import ImageSatellite


# Chemin relatif au dossier sentinel (depuis BASE_DIR)
SENTINEL_RELATIVE_PATH = os.path.join("module1_urbanisme", "data_use", "sentinel")


class Command(BaseCommand):
    help = "Importe les images Sentinel-2 depuis le dossier sentinel"

    def add_arguments(self, parser):
        parser.add_argument(
            "--folder", type=str,
            default=None,
            help=(
                "Dossier contenant les images Sentinel "
                "(par défaut : <BASE_DIR>/module1_urbanisme/data_use/sentinel)"
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les images à importer sans créer en base",
        )

    # ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        # CORRECTIF A8 : chemin absolu via settings.BASE_DIR
        if options["folder"]:
            folder_path = os.path.abspath(options["folder"])
        else:
            folder_path = os.path.join(str(settings.BASE_DIR), SENTINEL_RELATIVE_PATH)

        dry_run = options["dry_run"]

        self.stdout.write(f"Import des images Sentinel depuis : {folder_path}")

        if not os.path.exists(folder_path):
            self.stdout.write(self.style.ERROR(f"Dossier introuvable : {folder_path}"))
            return

        images_by_date = self._analyze_sentinel_files(folder_path)

        if not images_by_date:
            self.stdout.write(self.style.WARNING("Aucune image Sentinel trouvée"))
            return

        self.stdout.write(f"Images trouvées pour {len(images_by_date)} date(s) :")
        for date_str, files in sorted(images_by_date.items()):
            bands_found = list(files["bands"].keys())
            self.stdout.write(f"  {date_str} — Bandes : {bands_found}")

        imported_count = 0
        for date_str, files in sorted(images_by_date.items()):
            try:
                if not dry_run:
                    image = self._create_image_record(date_str, files)
                    self.stdout.write(self.style.SUCCESS(f"Créé : {image}"))
                else:
                    self.stdout.write(f"[DRY-RUN] Importerait : {date_str}")
                imported_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur import {date_str} : {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"\n=== RÉSUMÉ IMPORT ==="))
        self.stdout.write(f"Images importées : {imported_count}")

        if not dry_run:
            self._print_statistics()

    # ─────────────────────────────────────────────────────────────────────
    def _analyze_sentinel_files(self, folder_path: str) -> dict:
        """Analyse les fichiers TIFF Sentinel dans le dossier et les groupe par date."""
        images_by_date: dict = {}

        try:
            for filename in sorted(os.listdir(folder_path)):
                if not filename.lower().endswith(".tiff"):
                    continue

                file_info = self._parse_sentinel_filename(filename)
                if not file_info:
                    continue

                date_str = file_info["date"]
                if date_str not in images_by_date:
                    images_by_date[date_str] = {
                        "date": file_info["date_obj"],
                        "bands": {},
                        "classification": None,
                    }

                # CORRECTIF A8 : stocker le chemin ABSOLU du fichier
                abs_path = os.path.join(folder_path, filename)

                if "classification_map" in filename.lower():
                    images_by_date[date_str]["classification"] = abs_path
                elif "B04" in filename:
                    images_by_date[date_str]["bands"]["B04"] = abs_path
                elif "B08" in filename:
                    images_by_date[date_str]["bands"]["B08"] = abs_path
                elif "B11" in filename:
                    images_by_date[date_str]["bands"]["B11"] = abs_path
                elif "B12" in filename:
                    images_by_date[date_str]["bands"]["B12"] = abs_path

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur analyse dossier : {str(e)}"))

        return images_by_date

    def _parse_sentinel_filename(self, filename: str) -> dict | None:
        """
        Parse le nom de fichier Sentinel-2.
        Format attendu : 2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B08_(Raw).tiff
        """
        try:
            parts = filename.replace(".tiff", "").split("_")
            if len(parts) < 4:
                return None

            # Extraction de la date depuis la première partie (2024-01-29-00-00)
            date_parts = parts[0].split("-")
            year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            date_obj = date(year, month, day)

            return {
                "date": date_obj.strftime("%Y-%m-%d"),
                "date_obj": date_obj,
                "filename": filename,
            }
        except (IndexError, ValueError):
            return None

    def _create_image_record(self, date_str: str, files: dict) -> ImageSatellite:
        """
        Crée un enregistrement ImageSatellite avec les chemins absolus des bandes.
        Vérifie les bandes minimales B08 et B11 (B04 optionnel pour BSI).
        """
        bands = files["bands"]

        # Bandes obligatoires pour le calcul NDBI
        required = ["B08", "B11"]
        missing = [b for b in required if b not in bands]
        if missing:
            raise ValueError(
                f"Bandes obligatoires manquantes pour {date_str} : {missing}. "
                f"Bandes disponibles : {list(bands.keys())}"
            )

        # Vérification que les fichiers existent bien
        for band, path in bands.items():
            if not os.path.exists(path):
                self.stdout.write(
                    self.style.WARNING(f"  ⚠️  Fichier bande {band} introuvable : {path}")
                )

        image = ImageSatellite.objects.create(
            date_acquisition=files["date"],
            satellite="Sentinel-2_L2A",
            bands=bands,                        # ← chemins ABSOLUS (CORRECTIF A8)
            classification_map=files.get("classification"),
            processed=False,
        )
        return image

    def _print_statistics(self):
        """Affiche les statistiques d'import."""
        self.stdout.write(self.style.SUCCESS("\n=== STATISTIQUES ==="))
        total = ImageSatellite.objects.count()
        self.stdout.write(f"Total images en base : {total}")

        self.stdout.write("Dates disponibles :")
        for img in ImageSatellite.objects.order_by("date_acquisition"):
            bandes = list(img.bands.keys()) if img.bands else []
            self.stdout.write(
                f"  {img.date_acquisition} — Bandes : {bandes} — "
                f"{'✅ traitée' if img.processed else '⏳ non traitée'}"
            )
