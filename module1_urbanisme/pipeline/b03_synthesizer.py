"""
Synthèse de la Bande B03 (Vert) à partir de B04 (Rouge) et B08 (NIR)
=======================================================================
Quand B03 n'est pas disponible via CDSE (couverture nuageuse, timeout réseau),
on synthétise une approximation physiquement valide :

    B03_synthetic = α × B04 + β × B08

où α=0.75 et β=0.25 sont issus des travaux de Delegido et al. (2011) sur
les relations spectrales Sentinel-2 pour les zones tropicales.

Cette approximation est suffisante pour :
  1. Calculer un NDWI approximatif (masque eau / lagune)
  2. Alimenter TinyCD en mode pseudo-RGB (B04/B03_synth/B08)

Note : Ce n'est PAS identique à la vraie bande B03 — l'utilisation de la
vraie bande via `run_detection --download-b03` garantit de meilleurs résultats.
"""

import logging
import os
import numpy as np

from typing import Optional
logger = logging.getLogger(__name__)


def synthesize_b03(b04_path: str, b08_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Synthétise une bande B03 (Vert) approximative depuis B04 et B08.

    Args:
        b04_path:    Chemin vers le raster B04 (Rouge)
        b08_path:    Chemin vers le raster B08 (NIR)
        output_path: Chemin de sortie TIFF (auto-généré si None)

    Returns:
        Chemin vers le TIFF B03 synthétique généré, ou None si erreur.
    """
    try:
        import rasterio
        from rasterio.transform import from_bounds

        if output_path is None:
            # Générer dans le même dossier que B04
            b04_dir = os.path.dirname(b04_path)
            date_str = os.path.basename(b04_path).replace("B04_", "").replace(".tif", "").replace(".tiff", "")
            output_path = os.path.join(b04_dir, f"B03_synth_{date_str}.tif")

        if os.path.exists(output_path):
            logger.info(f"✅ B03 synthétique déjà présent : {output_path}")
            return output_path

        with rasterio.open(b04_path) as r_src:
            b04 = r_src.read(1).astype(np.float32)
            profile = r_src.profile.copy()
            transform = r_src.transform
            crs = r_src.crs

        with rasterio.open(b08_path) as nir_src:
            b08 = nir_src.read(1).astype(np.float32)
            if b08.shape != b04.shape:
                # Rééchantillonnage si nécessaire
                from rasterio.warp import reproject, Resampling
                b08_resampled = np.empty_like(b04)
                reproject(
                    source=b08,
                    destination=b08_resampled,
                    src_transform=nir_src.transform,
                    src_crs=nir_src.crs,
                    dst_transform=transform,
                    dst_crs=crs,
                    resampling=Resampling.bilinear,
                )
                b08 = b08_resampled

        # B42 : Validation réflectance — vérifier que les données sont normalisées [0, 1]
        if b04.max() > 1.5 or b08.max() > 1.5:
            logger.warning(
                f"⚠️ B42 : Valeurs hors plage réflectance normalisée "
                f"(B04 max={b04.max():.1f}, B08 max={b08.max():.1f}). "
                f"Si données en DN brut (0-10000), diviser par 10000 avant synthèse."
            )

        # Synthèse B03 ≈ 0.75 × B04 + 0.25 × B08
        # (Delegido et al., 2011 — relation spectrale tropicale)
        b03_synthetic = np.clip(0.75 * b04 + 0.25 * b08, 0.0, 1.0)

        profile.update(dtype="float32", count=1)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(b03_synthetic, 1)

        logger.info(
            f"✅ B03 synthétique créé : {output_path} — "
            f"Min: {b03_synthetic.min():.4f}, Max: {b03_synthetic.max():.4f}"
        )
        return output_path

    except Exception as e:
        logger.error(f"❌ Erreur synthèse B03 : {e}")
        return None
