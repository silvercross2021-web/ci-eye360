"""
Algorithmes de calcul NDBI et BSI pour la détection de constructions
Module 1 Urbanisme - CIV-Eye

CORRECTIFS APPLIQUÉS:
  - A4 : BSI utilise nir_data (B08) au lieu de red_data (B04) — formule (B11-B08)/(B11+B08)
  - A5 : detect_construction_changes() accepte des chemins explicites par bande
"""

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class NDBICalculator:
    """Calculateur d'indices spectraux pour la détection de constructions."""

    def __init__(self):
        self.threshold_built = 0.2   # Seuil NDBI bâti
        self.threshold_soil = 0.15   # Seuil BSI sol nu

    # ─────────────────────────────────────────────────────────────────────
    # CALCUL NDBI
    # ─────────────────────────────────────────────────────────────────────
    def calculate_ndbi(self, b08_path: str, b11_path: str) -> np.ndarray:
        """
        Calcule l'indice NDBI (Normalized Difference Built-up Index).

        NDBI = (SWIR1 - NIR) / (SWIR1 + NIR) = (B11 - B08) / (B11 + B08)
        Valeurs positives ⇒ surfaces bâties ou sol nu réfléchissant.

        Args:
            b08_path: Chemin vers le raster B08 (NIR, ~10m)
            b11_path: Chemin vers le raster B11 (SWIR1, ~20m)

        Returns:
            Tableau numpy 2D, valeurs dans [-1, 1].
        """
        try:
            with rasterio.open(b08_path) as nir_src, rasterio.open(b11_path) as swir_src:
                nir_data = nir_src.read(1).astype(float)
                swir_data = swir_src.read(1).astype(float)

                # Aligner les résolutions si nécessaire (B08=10m, B11=20m)
                if nir_data.shape != swir_data.shape:
                    logger.warning(
                        f"Dimensions différentes : NIR {nir_data.shape} vs SWIR {swir_data.shape}"
                        f" → rééchantillonnage..."
                    )
                    swir_data = self._resample_to_match(swir_src, nir_src)

                # NDBI = (B11 - B08) / (B11 + B08)
                with np.errstate(divide='ignore', invalid='ignore'):
                    ndbi = np.where(
                        (swir_data + nir_data) == 0,
                        0.0,
                        (swir_data - nir_data) / (swir_data + nir_data),
                    )

                ndbi = np.nan_to_num(ndbi, nan=0.0, posinf=1.0, neginf=-1.0)
                ndbi = np.clip(ndbi, -1.0, 1.0)

                logger.info(
                    f"NDBI calculé — Shape: {ndbi.shape}, "
                    f"Min: {ndbi.min():.3f}, Max: {ndbi.max():.3f}, "
                    f"Pixels bâtis (>0.2): {np.sum(ndbi > 0.2):,}"
                )
                return ndbi

        except Exception as e:
            logger.error(f"Erreur calcul NDBI: {str(e)}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # CALCUL BSI — CORRECTIF A4
    # ─────────────────────────────────────────────────────────────────────
    def calculate_bsi(self, b04_path: str, b08_path: str, b11_path: str) -> np.ndarray:
        """
        Calcule l'indice BSI simplifié (Bare Soil Index) pour détecter les terrassements.

        Formule conforme au plan v2.0 :
            BSI_approx = (B11 - B08) / (B11 + B08)

        CORRECTIF A4 : utilise B08 (NIR) en dénominateur et non B04 (Red).
        La signature conserve b04_path pour compatibilité API mais il n'est pas utilisé
        dans cette variante simplifiée. Il sera utile si B02 devient disponible pour
        implémenter la formule BSI complète : ((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02)).

        Args:
            b04_path: Chemin vers B04 (Red) — conservé pour compatibilité
            b08_path: Chemin vers B08 (NIR)
            b11_path: Chemin vers B11 (SWIR1)

        Returns:
            Tableau numpy 2D, valeurs dans [-1, 1].
        """
        try:
            with rasterio.open(b08_path) as nir_src, rasterio.open(b11_path) as swir_src:
                nir_data = nir_src.read(1).astype(float)    # B08 — NIR
                swir_data = swir_src.read(1).astype(float)  # B11 — SWIR1

                # Aligner les résolutions si nécessaire
                if swir_data.shape != nir_data.shape:
                    logger.warning("BSI : rééchantillonnage B11 → B08...")
                    swir_data = self._resample_to_match(swir_src, nir_src)

                # BSI_approx = (B11 - B08) / (B11 + B08)  ← CORRECTIF A4
                with np.errstate(divide='ignore', invalid='ignore'):
                    bsi = np.where(
                        (swir_data + nir_data) == 0,
                        0.0,
                        (swir_data - nir_data) / (swir_data + nir_data),
                    )

                bsi = np.nan_to_num(bsi, nan=0.0, posinf=1.0, neginf=-1.0)
                bsi = np.clip(bsi, -1.0, 1.0)

                logger.info(
                    f"BSI calculé (B11-B08)/(B11+B08) — Shape: {bsi.shape}, "
                    f"Min: {bsi.min():.3f}, Max: {bsi.max():.3f}, "
                    f"Pixels sol nu (>0.15): {np.sum(bsi > 0.15):,}"
                )
                return bsi

        except Exception as e:
            logger.error(f"Erreur calcul BSI: {str(e)}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # DÉTECTION DES CHANGEMENTS
    # ─────────────────────────────────────────────────────────────────────
    def detect_changes(
        self,
        ndbi_t1: np.ndarray,
        ndbi_t2: np.ndarray,
        bsi_t2: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Détecte les changements entre T1 et T2.

        Args:
            ndbi_t1: NDBI période de référence (2024)
            ndbi_t2: NDBI période de détection (2025)
            bsi_t2:  BSI période de détection (optionnel)

        Returns:
            Dict avec masques booléens :
              - 'new_constructions' : nouveaux bâtiments
              - 'soil_activity'     : terrassements
              - 'all_changes'       : union des deux
        """
        try:
            if ndbi_t1.shape != ndbi_t2.shape:
                raise ValueError(
                    f"Dimensions incompatibles : T1={ndbi_t1.shape} vs T2={ndbi_t2.shape}. "
                    f"Assurer que les deux images couvrent la même zone."
                )

            # Nouvelles constructions : NDBI passe de ≤0.2 à >0.2
            new_constructions = (ndbi_t2 > self.threshold_built) & (ndbi_t1 <= self.threshold_built)

            # Activité sol (terrassement)
            if bsi_t2 is not None:
                soil_activity = (bsi_t2 > self.threshold_soil) & (ndbi_t2 <= self.threshold_built)
            else:
                # Sans BSI : utiliser NDBI seul pour détecter les changements modérés
                soil_activity = (
                    (ndbi_t2 > self.threshold_soil)
                    & (ndbi_t2 <= self.threshold_built)
                    & (ndbi_t1 <= self.threshold_soil)
                )

            all_changes = new_constructions | soil_activity

            total = ndbi_t1.size
            logger.info(
                f"Détection changements:\n"
                f"  Nouvelles constructions : {np.sum(new_constructions):,} px "
                f"({100 * np.mean(new_constructions):.2f}%)\n"
                f"  Activité sol            : {np.sum(soil_activity):,} px "
                f"({100 * np.mean(soil_activity):.2f}%)\n"
                f"  Total changements       : {np.sum(all_changes):,} / {total:,} px"
            )

            return {
                'new_constructions': new_constructions,
                'soil_activity': soil_activity,
                'all_changes': all_changes,
            }

        except Exception as e:
            logger.error(f"Erreur détection changements: {str(e)}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # EXTRACTION DES RÉGIONS
    # ─────────────────────────────────────────────────────────────────────
    def extract_change_regions(
        self, change_mask: np.ndarray, min_size: int = 10
    ) -> list:
        """
        Extrait les régions connexes à partir d'un masque de changement.

        Args:
            change_mask: Tableau booléen 2D
            min_size:    Taille minimale en pixels pour conserver une région

        Returns:
            Liste de dicts décrivant chaque région (bbox, centroid, size_pixels).
        """
        try:
            from scipy import ndimage

            labeled, num_features = ndimage.label(change_mask)
            regions = []

            for i in range(1, num_features + 1):
                region_mask = labeled == i
                region_size = int(np.sum(region_mask))

                if region_size < min_size:
                    continue

                coords = np.where(region_mask)
                min_row, max_row = int(coords[0].min()), int(coords[0].max())
                min_col, max_col = int(coords[1].min()), int(coords[1].max())

                regions.append(
                    {
                        'label': i,
                        'size_pixels': region_size,
                        'bbox': (min_row, min_col, max_row, max_col),
                        'centroid': (
                            int(np.mean(coords[0])),
                            int(np.mean(coords[1])),
                        ),
                    }
                )

            logger.info(
                f"Extraction régions : {num_features} composantes, "
                f"{len(regions)} retenues (≥{min_size} px)"
            )
            return regions

        except ImportError:
            logger.warning("SciPy indisponible — extraction simplifiée (1 seule région)")
            coords = np.where(change_mask)
            if len(coords[0]) == 0:
                return []
            return [
                {
                    'label': 1,
                    'size_pixels': int(len(coords[0])),
                    'bbox': (
                        int(coords[0].min()), int(coords[1].min()),
                        int(coords[0].max()), int(coords[1].max()),
                    ),
                    'centroid': (int(np.mean(coords[0])), int(np.mean(coords[1]))),
                }
            ]

        except Exception as e:
            logger.error(f"Erreur extraction régions: {str(e)}")
            return []

    # ─────────────────────────────────────────────────────────────────────
    # RÉÉCHANTILLONNAGE
    # ─────────────────────────────────────────────────────────────────────
    def _resample_to_match(self, source_src, target_src) -> np.ndarray:
        """
        Rééchantillonne le raster source pour correspondre à la grille du raster cible.
        Utilisé pour aligner B11 (20m) sur B08 (10m).
        """
        target_shape = target_src.shape
        resampled = np.empty(target_shape, dtype=np.float64)

        reproject(
            source=rasterio.band(source_src, 1),
            destination=resampled,
            src_transform=source_src.transform,
            src_crs=source_src.crs,
            dst_transform=target_src.transform,
            dst_crs=target_src.crs,
            resampling=Resampling.bilinear,  # Bilinear pour données continues
        )
        return resampled

    # ─────────────────────────────────────────────────────────────────────
    # METADATA DU RASTER
    # ─────────────────────────────────────────────────────────────────────
    def get_raster_transform(self, raster_path: str):
        """Retourne le transform affine d'un raster (pour conversion pixel → WGS84)."""
        with rasterio.open(raster_path) as src:
            return src.transform, src.crs, src.bounds


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires (API simplifiée)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_ndbi_for_period(b08_path: str, b11_path: str) -> np.ndarray:
    """Calcule le NDBI pour une période (alias simplifié)."""
    return NDBICalculator().calculate_ndbi(b08_path, b11_path)


def calculate_bsi_for_period(b04_path: str, b08_path: str, b11_path: str) -> np.ndarray:
    """Calcule le BSI pour une période (alias simplifié)."""
    return NDBICalculator().calculate_bsi(b04_path, b08_path, b11_path)


def detect_construction_changes(
    b08_t1_path: str,
    b11_t1_path: str,
    b08_t2_path: str,
    b11_t2_path: str,
    b04_t2_path: str = None,
    b08_bsi_path: str = None,
    b11_bsi_path: str = None,
) -> Dict:
    """
    Pipeline complet de détection des changements avec chemins explicites par bande.

    CORRECTIF A5 : remplace l'ancienne version avec remplacement de chaînes fragile.

    Args:
        b08_t1_path: Chemin B08 (NIR) image T1
        b11_t1_path: Chemin B11 (SWIR) image T1
        b08_t2_path: Chemin B08 (NIR) image T2
        b11_t2_path: Chemin B11 (SWIR) image T2
        b04_t2_path: Chemin B04 (Red) image T2 — pour BSI (optionnel, peut être None)
        b08_bsi_path: Chemin B08 pour BSI (si None, utilise b08_t2_path)
        b11_bsi_path: Chemin B11 pour BSI (si None, utilise b11_t2_path)

    Returns:
        Dict avec masques 'new_constructions', 'soil_activity', 'all_changes'.
    """
    calc = NDBICalculator()

    ndbi_t1 = calc.calculate_ndbi(b08_t1_path, b11_t1_path)
    ndbi_t2 = calc.calculate_ndbi(b08_t2_path, b11_t2_path)

    bsi_t2 = None
    b08_for_bsi = b08_bsi_path or b08_t2_path
    b11_for_bsi = b11_bsi_path or b11_t2_path
    if b08_for_bsi and b11_for_bsi:
        bsi_t2 = calc.calculate_bsi(b04_t2_path, b08_for_bsi, b11_for_bsi)

    return calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2)
