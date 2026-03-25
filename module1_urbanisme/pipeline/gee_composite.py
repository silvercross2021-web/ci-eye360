"""
Compositing multi-temporel Sentinel-2 via Google Earth Engine — Phase 4
Module 1 Urbanisme - CIV-Eye

Crée un composite médian sans nuages à partir de 5-10 images de saison sèche.
Saison sèche Côte d'Ivoire : Novembre → Mars (moins de nuages).

Usage :
    from module1_urbanisme.pipeline.gee_composite import GEECompositor
    compositor = GEECompositor()
    bands = compositor.get_composite(year=2024)
    # → {"B04": np.array, "B08": np.array, "B11": np.array, "SCL_proxy": np.array}
"""

import logging
import os
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Coordonnées Treichville / Abidjan (BBOX WGS84)
TREICHVILLE_BBOX = [-4.03001, 5.28501, -3.97301, 5.32053]

# Saison sèche Côte d'Ivoire : 01-Nov → 31-Mar
DRY_SEASON_START = "11-01"   # dd-mm → "{year}-11-01"
DRY_SEASON_END   = "03-31"   # couvre Novembre → Mars de l'année suivante


class GEECompositor:
    """
    Compositeur GEE pour Sentinel-2 L2A.
    Crée un composite médian anti-nuage sur la saison sèche.
    """

    def __init__(self):
        self._initialized = False
        self._init_gee()

    # ─────────────────────────────────────────────────────────────────────
    # INIT GEE
    # ─────────────────────────────────────────────────────────────────────
    def _init_gee(self):
        """Initialise Earth Engine avec le projet Cloud configuré."""
        try:
            import ee
            # Projet GEE à définir dans .env (ex: "mon-projet-gee")
            project_id = os.getenv("GEE_PROJECT_ID", "").strip()
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
            self._initialized = True
            logger.info("Google Earth Engine : initialisé avec succès")
        except ImportError:
            logger.warning("earthengine-api non installé — pip install earthengine-api")
        except Exception as e:
            logger.warning(
                f"GEE init échouée : {e}\n"
                f"Exécuter : earthengine authenticate\n"
                f"Puis ajouter GEE_PROJECT_ID=<ton-projet> dans .env"
            )

    # ─────────────────────────────────────────────────────────────────────
    # API PRINCIPALE
    # ─────────────────────────────────────────────────────────────────────
    def get_composite(
        self,
        year: int,
        bands: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        max_cloud_cover: float = 20.0,
    ) -> Dict[str, np.ndarray]:
        """
        Crée et retourne un composite médian Sentinel-2 pour une année donnée.

        Couvre la saison sèche : Nov(year-1) → Mar(year) pour "year".
        Ex: year=2024 → images de Nov 2023 à Mars 2024.

        Args:
            year:             Année de référence (ex: 2024 pour T1, 2025 pour T2)
            bands:            Bandes à retourner (défaut: B04, B08, B11)
            bbox:             Zone [lon_min, lat_min, lon_max, lat_max] (défaut: Treichville)
            max_cloud_cover:  Couverture nuageuse max acceptée (%)

        Returns:
            Dict {band_name: np.ndarray} — tableaux 2D float32.
        """
        if not self._initialized:
            raise RuntimeError(
                "GEE non initialisé. Exécuter :\n"
                "  1. earthengine authenticate\n"
                "  2. Ajouter GEE_PROJECT_ID dans .env"
            )

        if bands is None:
            bands = ["B04", "B08", "B11"]
        if bbox is None:
            bbox = TREICHVILLE_BBOX

        import ee
        import requests

        region = ee.Geometry.Rectangle(bbox)

        # Saison sèche : Nov de l'année précédente → Mars de l'année courante
        # BUG-009 : Utiliser les constantes DRY_SEASON_START/_END
        date_start = f"{year - 1}-{DRY_SEASON_START}"
        date_end   = f"{year}-{DRY_SEASON_END}"

        logger.info(
            f"GEE composite — Période: {date_start} → {date_end} | "
            f"Cloud < {max_cloud_cover}% | Bandes: {bands}"
        )

        # ── Construire la collection Sentinel-2 L2A ─────────────────────
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region)
            .filterDate(date_start, date_end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
            .map(self._mask_clouds_s2)
        )

        count = collection.size().getInfo()
        logger.info(f"GEE : {count} images trouvées après filtrage nuages")

        if count == 0:
            raise ValueError(
                f"Aucune image Sentinel-2 trouvée pour {date_start}→{date_end} "
                f"avec cloud < {max_cloud_cover}%"
            )

        # ── Composite médian ─────────────────────────────────────────────
        composite = collection.median()

        # ── Extraction des bandes comme numpy arrays ─────────────────────
        result = {}
        for band_name in bands:
            gee_band = band_name  # B04, B08, B11 directement
            try:
                band_image = composite.select(gee_band).clip(region)

                # Obtenir les dimensions de la région
                scale = 10 if band_name in ["B04", "B08"] else 20

                # Exporter comme GeoTIFF via getDownloadURL (format supporté par l'API GEE)
                pixels = band_image.getDownloadURL({
                    "scale": scale,
                    "crs": "EPSG:4326",
                    "region": region,
                    "format": "GEO_TIFF",
                })

                response = requests.get(pixels)
                import io, rasterio
                with rasterio.open(io.BytesIO(response.content)) as src:
                    arr = src.read(1).astype(np.float32)
                # Normaliser DN → réflectance
                arr = arr / 10000.0
                arr = np.clip(arr, 0.0, 1.0)
                result[band_name] = arr
                logger.info(f"GEE : bande {band_name} extraite — shape={arr.shape}")

            except Exception as e:
                logger.error(f"GEE : erreur extraction bande {band_name} : {e}")

        return result

    # ─────────────────────────────────────────────────────────────────────
    # MASQUE NUAGES SCL Sentinel-2
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _mask_clouds_s2(image):
        """
        Applique le masque SCL Sentinel-2 L2A.
        Classes gardées : [4] végétation, [5] sol nu, [6] eau, [11] neige
        Classes masquées : [3] ombre, [8][9][10] nuages
        """
        import ee
        scl = image.select("SCL")
        mask = (
            scl.neq(3)   # ombre de nuage
            .And(scl.neq(8))   # nuage moyen
            .And(scl.neq(9))   # nuage dense
            .And(scl.neq(10))  # cirrus
        )
        return image.updateMask(mask)

    # ─────────────────────────────────────────────────────────────────────
    # T1 ET T2 PRÊTS POUR LE PIPELINE
    # ─────────────────────────────────────────────────────────────────────
    def get_t1_and_t2_composites(
        self,
        year_t1: int = 2024,
        year_t2: int = 2025,
        bands: Optional[List[str]] = None,
        max_cloud_cover: float = 20.0,
    ) -> tuple:
        """
        Retourne les composites T1 et T2 prêts pour le pipeline NDBI.

        Returns:
            Tuple (bands_t1_dict, bands_t2_dict)
        """
        if bands is None:
            bands = ["B04", "B08", "B11"]

        logger.info(f"Composites GEE : T1=saison sèche {year_t1}, T2=saison sèche {year_t2}")
        bands_t1 = self.get_composite(year_t1, bands, max_cloud_cover=max_cloud_cover)
        bands_t2 = self.get_composite(year_t2, bands, max_cloud_cover=max_cloud_cover)
        return bands_t1, bands_t2

    # ─────────────────────────────────────────────────────────────────────
    # DIAGNOSTIC
    # ─────────────────────────────────────────────────────────────────────
    def status(self) -> Dict:
        """Retourne l'état de la connexion GEE."""
        if not self._initialized:
            return {
                "initialized": False,
                "message": "earthengine authenticate requis",
                "steps": [
                    "1. pip install earthengine-api",
                    "2. earthengine authenticate (dans un terminal séparé)",
                    "3. Ajouter GEE_PROJECT_ID=<votre-projet> dans .env",
                ],
            }
        try:
            import ee
            img_count = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(ee.Geometry.Rectangle(TREICHVILLE_BBOX))
                .filterDate("2024-01-01", "2024-12-31")
                .size()
                .getInfo()
            )
            return {
                "initialized": True,
                "images_available_2024": img_count,
                "region": "Treichville (BBOX Abidjan)",
            }
        except Exception as e:
            return {"initialized": True, "error": str(e)}
