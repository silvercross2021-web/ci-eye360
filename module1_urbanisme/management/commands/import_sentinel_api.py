"""
Script d'importation automatique Sentinel-2 via API (Phase 3 & 4)
Télécharge les bandes satellitaires, crée les TIFF physiques géoréférencés 
et renseigne la base de données ImageSatellite.

Usage : python manage.py import_sentinel_api --date 2024-01-29
"""

import os
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from datetime import datetime
import numpy as np
# load_dotenv supprimé (BUG-013)

from django.core.management.base import BaseCommand
from django.conf import settings
from module1_urbanisme.models import ImageSatellite
from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher, TREICHVILLE_BBOX, BAND_RESOLUTION


class Command(BaseCommand):
    help = "Importe les images Sentinel-2 automatiques depuis Sentinel Hub / CDSE API"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, required=True, help="Date cible (ex: 2024-01-29)")
        parser.add_argument("--source", type=str, choices=["sh", "cdse", "pc"], default=None, 
                            help="Forcer une source spécifique")

    def handle(self, *args, **options):
        target_date = options["date"]
        
        self.stdout.write(f"🔄 Début acquisition API pour la date : {target_date}")
        
        # Initialiser le fetcher (qui va prioriser Sentinel Hub si .env ok)
        fetcher = SentinelDataFetcher()
        
        # Forcer la source si demandé (pour le debug)
        if options["source"] == "sh":
            fetcher._cdse_available = False
            fetcher._pc_available = False
        elif options["source"] == "cdse":
            fetcher._sh_available = False
            fetcher._pc_available = False
        elif options["source"] == "pc":
            fetcher._sh_available = False
            fetcher._cdse_available = False

        self.stdout.write(f"  > Statut API : {fetcher.status()}")

        try:
            # 1. Obtenir les arrays numpy (et la métadonnée cloud) via Mosaïquage Médian (fenêtre de 45 jours)
            bands_data = fetcher.get_bands_for_date(
                target_date, 
                bands=["B04", "B08", "B11", "SCL"],
                date_window_days=45
            )
            
            if not bands_data:
                self.stdout.write(self.style.ERROR(f"❌ Aucune image satisfaisante trouvée pour {target_date}"))
                return

            self.stdout.write(self.style.SUCCESS(f"✅ Bandes récupérées en mémoire !"))

            # 2. Préparer le dossier d'export
            export_dir = os.path.join(settings.BASE_DIR, "module1_urbanisme", "data_use", "sentinel_api_exports", target_date)
            os.makedirs(export_dir, exist_ok=True)
            self.stdout.write(f"  > Dossier d'export : {export_dir}")

            bands_paths = {}
            scl_path = None
            
            bbox = TREICHVILLE_BBOX

            # 3. Sauvegarder chaque numpy array en TIFF géoréférencé
            for band_name, arr in bands_data.items():
                res = BAND_RESOLUTION.get(band_name, 10)
                # Calcul de l'affine transform
                height, width = arr.shape
                transform = from_bounds(
                    bbox["min_lon"], bbox["min_lat"], 
                    bbox["max_lon"], bbox["max_lat"], 
                    width, height
                )
                
                output_path = os.path.join(export_dir, f"{band_name}_{target_date}.tif")
                
                # Profil TIFF
                profile = {
                    'driver': 'GTiff',
                    'height': height,
                    'width': width,
                    'count': 1,
                    # Les pixels sont en float32 (reflectance) sauf SCL (classes entières)
                    'dtype': rasterio.float32 if band_name != 'SCL' else rasterio.uint8,
                    'crs': '+proj=longlat +datum=WGS84 +no_defs', # WGS84 sans EPSG database lookup
                    'transform': transform,
                    'compress': 'lzw'
                }
                
                # SCL doit être forcé en uint8 pour la classe SCL
                if band_name == 'SCL':
                    arr = np.nan_to_num(arr).astype(np.uint8)
                else:
                    arr = np.nan_to_num(arr).astype(np.float32)

                with rasterio.open(output_path, 'w', **profile) as dst:
                    dst.write(arr, 1)

                if band_name == "SCL":
                    scl_path = output_path
                else:
                    bands_paths[band_name] = output_path

                self.stdout.write(f"    - Sauv. {band_name} : {output_path}")

            # 4. Enregistrer en base de données ImageSatellite
            acq_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            img, created = ImageSatellite.objects.update_or_create(
                date_acquisition=acq_date,
                defaults={
                    "bands": bands_paths,
                    "classification_map": scl_path,
                    "processed": False
                }
            )

            status = "CRÉÉE" if created else "MISE À JOUR"
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Image {status} en base de données : ID {img.id}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur critique : {e}"))
            import traceback
            traceback.print_exc()
