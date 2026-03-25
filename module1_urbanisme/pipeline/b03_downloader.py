"""
Téléchargement Automatique de B03 (Green) via CDSE Copernicus STAC
====================================================================
Ce module récupère la bande B03 (Green, 10m) nécessaire pour le calcul NDWI
(Masque Eau / Zone Lagunaire Abidjan — Amélioration L2).

SOURCE : Copernicus Data Space Ecosystem (CDSE) — 100% GRATUIT, SANS CLÉ.
Aucune installation de clé, aucun compte requis.

Usage :
    from module1_urbanisme.pipeline.b03_downloader import download_b03_cdse
    path_2024 = download_b03_cdse("2024-01-01", "2024-03-31")
    path_2025 = download_b03_cdse("2025-01-01", "2025-03-31")
    # → Chemin absolu vers le fichier TIFF B03 téléchargé
"""

import logging
import os
from datetime import datetime, timedelta

import numpy as np

from typing import Optional, List, Dict
logger = logging.getLogger(__name__)

# Zone Treichville — Abidjan (WGS84)
TREICHVILLE_BBOX = [-4.035, 5.285, -3.995, 5.325]


def download_b03_cdse(date_from: str, date_to: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    Télécharge la bande B03 (Green, 10m) de la meilleure image Sentinel-2 L2A
    disponible dans la fenêtre [date_from, date_to] pour Treichville.

    AUCUNE CLÉ REQUISE — utilise le catalogue public CDSE Copernicus.

    Args:
        date_from:  Date de début au format "YYYY-MM-DD"
        date_to:    Date de fin au format "YYYY-MM-DD"
        output_dir: Dossier de sortie (défaut: module1_urbanisme/data_use/sentinel/)

    Returns:
        Chemin absolu vers le fichier B03.tiff téléchargé, ou None si échec.
    """
    logger.info(f"⬇️  Téléchargement B03 (NDWI/masque eau) via CDSE — période {date_from} → {date_to}")

    try:
        import pystac_client
        import rasterio
        from rasterio.windows import from_bounds
    except ImportError as e:
        logger.error(
            f"❌ pystac-client ou rasterio non installé : {e}\n"
            f"   → Installez via : .\\venv\\Scripts\\pip install pystac-client rasterio"
        )
        return None

    # M22 : Dossier de sortie cohérent avec sentinel_api_exports/{date}/
    if output_dir is None:
        try:
            from django.conf import settings
            output_dir = os.path.join(
                settings.BASE_DIR, "module1_urbanisme", "data_use",
                "sentinel_api_exports", date_from
            )
        except Exception:
            output_dir = os.path.join(
                os.getcwd(), "module1_urbanisme", "data_use",
                "sentinel_api_exports", date_from
            )

    os.makedirs(output_dir, exist_ok=True)

    output_filename = f"B03_{date_from}.tif"
    output_path = os.path.join(output_dir, output_filename)

    if os.path.exists(output_path):
        logger.info(f"✅ B03 déjà présent : {output_path} — pas de re-téléchargement")
        return output_path

    try:
        # Connexion au catalogue CDSE — GRATUIT, SANS CLÉ
        logger.info("🔍 Connexion au catalogue CDSE STAC (gratuit, sans clé)...")
        catalog = pystac_client.Client.open(
            "https://catalogue.dataspace.copernicus.eu/stac"
        )

        # Recherche de la meilleure image avec peu de nuages
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=TREICHVILLE_BBOX,
            datetime=f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
            max_items=20,
        )

        items = list(search.items())
        if not items:
            logger.warning(
                f"⚠️  CDSE : Aucune image Sentinel-2 trouvée pour {date_from}→{date_to}\n"
                f"   → Vérifiez la connexion internet ou agrandissez la fenêtre de dates"
            )
            return None

        # Filtrer par couverture nuageuse côté Python (query STAC non supporté par CDSE)
        items = [i for i in items if i.properties.get("eo:cloud_cover", 100) <= 80]
        if not items:
            logger.warning(f"⚠️  CDSE : Toutes les images ont > 80% de nuages pour {date_from}→{date_to}")
            return None

        # Prendre la meilleure image
        items.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
        best_item = items[0]
        cloud_pct = best_item.properties.get("eo:cloud_cover", "?")
        best_date = best_item.datetime.strftime("%Y-%m-%d") if best_item.datetime else "?"

        logger.info(
            f"✅ Meilleure image trouvée : {best_date} — {cloud_pct}% de nuages"
        )

        # Trouver l'asset B03
        b03_key = None
        for key in ["B03", "B03_10m", "green"]:
            if key in best_item.assets:
                b03_key = key
                break

        if b03_key is None:
            logger.warning(
                f"⚠️  Bande B03 non trouvée dans l'item CDSE. Assets disponibles : "
                f"{list(best_item.assets.keys())}"
            )
            return None

        b03_href = best_item.assets[b03_key].href

        # Convertir S3 eodata → HTTPS public CDSE (évite AccessDenied sur S3 privé)
        if b03_href.startswith("s3://eodata/"):
            b03_href = b03_href.replace(
                "s3://eodata/",
                "https://eodata.dataspace.copernicus.eu/",
                1
            )
        logger.info(f"📡 Téléchargement B03 depuis : {b03_href[:80]}...")

        # Lecture et découpage sur la zone Treichville
        with rasterio.Env(GDAL_HTTP_UNSAFESSL='YES'):
            with rasterio.open(b03_href) as src:
                window = from_bounds(
                    TREICHVILLE_BBOX[0], TREICHVILLE_BBOX[1],
                    TREICHVILLE_BBOX[2], TREICHVILLE_BBOX[3],
                    transform=src.transform
                )
                b03_data = src.read(1, window=window).astype(np.float32)

                # Normaliser la réflectance DN → [0, 1]
                b03_data = np.where(b03_data > 0, b03_data / 10000.0, 0.0)

                # Métadonnées pour le TIFF de sortie
                transform = src.window_transform(window)
                profile = src.profile.copy()
                profile.update({
                    "driver": "GTiff",
                    "dtype": "float32",
                    "width": b03_data.shape[1],
                    "height": b03_data.shape[0],
                    "count": 1,
                    "transform": transform,
                    "crs": src.crs,
                })

        # Sauvegarder le TIFF B03
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(b03_data, 1)

        logger.info(
            f"✅ B03 sauvegardé : {output_path}\n"
            f"   Shape : {b03_data.shape}, Min : {b03_data.min():.4f}, Max : {b03_data.max():.4f}"
        )
        return output_path

    except Exception as e:
        logger.error(
            f"❌ Erreur téléchargement B03 : {e}\n"
            f"   → Vérifiez votre connexion internet ou réessayez plus tard"
        )
        return None


def calculate_ndwi_from_paths(b03_path: str, b08_path: str) -> np.ndarray | None:
    """
    Calcule l'indice NDWI (masque eau/lagunaire).

    NDWI = (B03 - B08) / (B03 + B08)
    Valeur > 0 = eau ou végétation aqueuse.

    Args:
        b03_path: Chemin vers le raster B03 (Green)
        b08_path: Chemin vers le raster B08 (NIR)

    Returns:
        Tableau numpy 2D NDWI, ou None si fichier manquant.
    """
    if b03_path is None or not os.path.exists(b03_path):
        logger.warning(
            "⚠️  B03 absent — masque NDWI (eau/lagunaire) désactivé\n"
            "   → Lancer download_b03_cdse() pour télécharger B03 automatiquement (GRATUIT)"
        )
        return None

    try:
        import rasterio
        from rasterio.warp import reproject, Resampling

        with rasterio.open(b03_path) as green_src, rasterio.open(b08_path) as nir_src:
            green_data = green_src.read(1).astype(np.float32)
            nir_data = nir_src.read(1).astype(np.float32)

            if green_data.shape != nir_data.shape:
                logger.info("🔧 Rééchantillonnage B03 → B08 pour NDWI...")
                nir_resampled = np.empty(green_data.shape, dtype=np.float32)
                reproject(
                    source=nir_data,
                    destination=nir_resampled,
                    src_transform=nir_src.transform,
                    src_crs=nir_src.crs,
                    dst_transform=green_src.transform,
                    dst_crs=green_src.crs,
                    resampling=Resampling.bilinear
                )
                nir_data = nir_resampled

        with np.errstate(divide='ignore', invalid='ignore'):
            ndwi = np.where(
                (green_data + nir_data) == 0, 0.0,
                (green_data - nir_data) / (green_data + nir_data)
            )

        ndwi = np.nan_to_num(ndwi, nan=0.0, posinf=1.0, neginf=-1.0)
        ndwi = np.clip(ndwi, -1.0, 1.0)

        water_pixels = np.sum(ndwi > 0)
        logger.info(
            f"✅ NDWI calculé — {water_pixels:,} pixels eau détectés (masque lagunaire actif)\n"
            f"   Min: {ndwi.min():.3f}, Max: {ndwi.max():.3f}"
        )
        return ndwi

    except Exception as e:
        logger.error(f"❌ Erreur calcul NDWI : {e}")
        return None
