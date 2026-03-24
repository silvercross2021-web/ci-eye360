"""
Algorithmes de calcul NDBI, BSI, NDVI et BUI pour la détection de constructions
Module 1 Urbanisme - CIV-Eye

CORRECTIFS APPLIQUÉS:
  - A4 : BSI utilise nir_data (B08) au lieu de red_data (B04) — formule (B11-B08)/(B11+B08)
  - A5 : detect_construction_changes() accepte des chemins explicites par bande

AMÉLIORATIONS APPORTÉES (phases 1 et 2) :
  - L1 : Détection des bâtiments rasés (delta NDBI négatif)
  - L3 : Masque NDVI pour éliminer les faux positifs végétation
  - L4 : Taille minimale/maximale des régions ajustée
  - L5 : Score de confiance calculé dynamiquement
  - L6 : Masque nuages via SCL (Scene Classification Layer)
  - Ph2: calculate_ndvi() + calculate_bui() disponibles
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
        # M21 : Seuils du masque de changement initial (filtre LARGE).
        # Le pipeline de vérification (verification_4_couches.py) applique ensuite
        # des seuils plus fins calibrés CIV (0.10 pour tôle/béton brut ivoirien).
        # Ne PAS abaisser ces seuils ici — risque de trop de faux positifs en amont.
        self.threshold_built = 0.2   # Seuil NDBI bâti (masque initial)
        self.threshold_soil = 0.15   # Seuil BSI sol nu (masque initial)

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
        ndvi_t2: Optional[np.ndarray] = None,
        bui_threshold: float = 0.0,
    ) -> Dict[str, np.ndarray]:
        """
        Détecte les changements entre T1 et T2.

        Args:
            ndbi_t1:       NDBI période de référence (2024)
            ndbi_t2:       NDBI période de détection (2025)
            bsi_t2:        BSI période de détection (optionnel)
            ndvi_t2:       NDVI T2 — si fourni, masque les pixels végétation > 0.4 (L3)
            bui_threshold: Seuil BUI minimal pour confirmer une construction (défaut 0.0 = désactivé)

        Returns:
            Dict avec masques booléens :
              - 'new_constructions' : nouveaux bâtiments (après masque NDVI si fourni)
              - 'soil_activity'     : terrassements
              - 'demolished'        : bâtiments rasés  (L1 — NOUVEAU)
              - 'all_changes'       : union des trois
        """
        try:
            if ndbi_t1.shape != ndbi_t2.shape:
                raise ValueError(
                    f"Dimensions incompatibles : T1={ndbi_t1.shape} vs T2={ndbi_t2.shape}. "
                    f"Assurer que les deux images couvrent la même zone."
                )

            # Masque eau global (utilisé sur tous les types de changement)
            # NDBI < -0.15 sur T1 OU T2 = eau/lagune = exclure de toute la détection
            water_proxy = (ndbi_t1 < -0.15) | (ndbi_t2 < -0.15)

            # ── Nouvelles constructions : NDBI passe de ≤0.2 à >0.2 ──────────
            new_constructions = (ndbi_t2 > self.threshold_built) & (ndbi_t1 <= self.threshold_built) & ~water_proxy

            # ── L3 : Masque végétation — éliminer faux positifs NDVI élevé ───
            if ndvi_t2 is not None:
                vegetation_mask = (ndvi_t2 > 0.4)  # NDVI > 0.4 = végétation dense
                new_constructions = new_constructions & ~vegetation_mask
                logger.info(
                    f"Masque NDVI (L3) appliqué — "
                    f"{np.sum(vegetation_mask):,} pixels végétation exclus"
                )

            # ── Activité sol (terrassement) ───────────────────────────────────
            # BUG#1 CORRIGÉ : masque eau ajouté (ndbi < -0.15 = eau/lagune)
            if bsi_t2 is not None:
                soil_activity = (bsi_t2 > self.threshold_soil) & (ndbi_t2 <= self.threshold_built) & ~water_proxy
            else:
                soil_activity = (
                    (ndbi_t2 > self.threshold_soil)
                    & (ndbi_t2 <= self.threshold_built)
                    & (ndbi_t1 <= self.threshold_soil)
                    & ~water_proxy
                )

            # ── L1 : Demolition — NDBI T1 élevé + T2 très bas ───────────────
            # NDBI_T1 > 0.25 (bâti en 2024) ET NDBI_T2 < 0.05 (plus bâti en 2025)
            # CORRECTION COMPLÈTE : exclure l'eau pour éviter les fausses démolitions saisonnières
            demolished = (ndbi_t1 > 0.25) & (ndbi_t2 < 0.05) & ~water_proxy
            logger.info(
                f"Démolitions détectées (L1) : {np.sum(demolished):,} pixels (eau exclue)"
            )

            all_changes = new_constructions | soil_activity | demolished

            total = ndbi_t1.size
            logger.info(
                f"Détection changements:\n"
                f"  Nouvelles constructions : {np.sum(new_constructions):,} px "
                f"({100 * np.mean(new_constructions):.2f}%)\n"
                f"  Activité sol            : {np.sum(soil_activity):,} px "
                f"({100 * np.mean(soil_activity):.2f}%)\n"
                f"  Bâtiments rasés (L1)    : {np.sum(demolished):,} px "
                f"({100 * np.mean(demolished):.2f}%)\n"
                f"  Total changements       : {np.sum(all_changes):,} / {total:,} px"
            )

            return {
                'new_constructions': new_constructions,
                'soil_activity': soil_activity,
                'demolished': demolished,       # ← L1 NOUVEAU
                'all_changes': all_changes,
            }

        except Exception as e:
            logger.error(f"Erreur détection changements: {str(e)}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # EXTRACTION DES RÉGIONS
    # ─────────────────────────────────────────────────────────────────────
    def extract_change_regions(
        self, change_mask: np.ndarray, min_size: int = 2, max_size: int = 500
    ) -> list:
        """
        Extrait les régions connexes à partir d'un masque de changement.

        L4 — Taille ajustée :
          - min_size=2 pixels (≈200m² à 10m/pixel Sentinel-2 — petite construction Treichville)
          - max_size=500 pixels (filtre les grandes zones uniformes : routes, parkings)

        Args:
            change_mask: Tableau booléen 2D
            min_size:    Taille minimale en pixels (défaut 2, soit ~200m² à 10m/pixel)
            max_size:    Taille maximale en pixels (défaut 500, filtre faux positifs routes)

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

                # L4 : filtrer par taille minimale ET maximale
                if region_size < min_size or region_size > max_size:
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
    # CALCUL NDVI — Phase 2
    # ─────────────────────────────────────────────────────────────────────
    def calculate_ndvi(self, b04_path: str, b08_path: str) -> np.ndarray:
        """
        Calcule l'indice NDVI (Normalized Difference Vegetation Index).

        NDVI = (NIR - Red) / (NIR + Red) = (B08 - B04) / (B08 + B04)
        Valeurs > 0.4 → végétation dense (masque L3 dans detect_changes).

        Args:
            b04_path: Chemin vers le raster B04 (Red, ~10m)
            b08_path: Chemin vers le raster B08 (NIR, ~10m)

        Returns:
            Tableau numpy 2D, valeurs dans [-1, 1].
        """
        try:
            with rasterio.open(b04_path) as red_src, rasterio.open(b08_path) as nir_src:
                red_data = red_src.read(1).astype(float)
                nir_data = nir_src.read(1).astype(float)

                # Aligner si nécessaire
                if red_data.shape != nir_data.shape:
                    logger.warning("NDVI : rééchantillonnage B04 → B08...")
                    red_data = self._resample_to_match(red_src, nir_src)

                # NDVI = (B08 - B04) / (B08 + B04)
                with np.errstate(divide='ignore', invalid='ignore'):
                    ndvi = np.where(
                        (nir_data + red_data) == 0,
                        0.0,
                        (nir_data - red_data) / (nir_data + red_data),
                    )

                ndvi = np.nan_to_num(ndvi, nan=0.0, posinf=1.0, neginf=-1.0)
                ndvi = np.clip(ndvi, -1.0, 1.0)

                logger.info(
                    f"NDVI calculé — Shape: {ndvi.shape}, "
                    f"Min: {ndvi.min():.3f}, Max: {ndvi.max():.3f}, "
                    f"Pixels végétation (>0.4): {np.sum(ndvi > 0.4):,}"
                )
                return ndvi

        except Exception as e:
            logger.error(f"Erreur calcul NDVI: {str(e)}")
            raise

    # ─────────────────────────────────────────────────────────────────────
    # CALCUL BUI — Phase 2
    # ─────────────────────────────────────────────────────────────────────
    def calculate_bui(self, ndbi: np.ndarray, ndvi: np.ndarray) -> np.ndarray:
        """
        Calcule le BUI (Built-Up Index) = NDBI - NDVI.

        Avantage : supprime automatiquement les faux positifs végétation.
        Un pixel avec fort NDBI ET fort NDVI (végétation sur toit) → BUI faible.
        Un vrai bâtiment : NDBI > 0 et NDVI < 0 → BUI élevé.

        Args:
            ndbi: Tableau NDBI numpy (valeurs [-1, 1])
            ndvi: Tableau NDVI numpy de MÊME dimension

        Returns:
            Tableau BUI numpy, valeurs clippées dans [-1, 1].
        """
        if ndbi.shape != ndvi.shape:
            raise ValueError(
                f"NDBI {ndbi.shape} et NDVI {ndvi.shape} ont des dimensions différentes"
            )
        bui = np.clip(ndbi - ndvi, -1.0, 1.0)
        logger.info(
            f"BUI calculé — Min: {bui.min():.3f}, Max: {bui.max():.3f}, "
            f"Pixels bâtis confirmés (>0.05): {np.sum(bui > 0.05):,}"
        )
        return bui

    # ─────────────────────────────────────────────────────────────────────
    # MASQUE SCL (nuages) — L6
    # ─────────────────────────────────────────────────────────────────────
    def apply_scl_mask(
        self, array: np.ndarray, scl_path: str,
        invalid_classes: tuple = (3, 6, 8, 9, 10)
    ) -> np.ndarray:
        """
        Masque les pixels invalides (nuages, ombres) définis par le SCL Sentinel-2.

        Classes SCL invalides par défaut :
          3  = ombre de nuage
          8  = nuage de densité moyenne
          9  = nuage dense
          10 = cirrus

        Les pixels masqués sont mis à NaN pour être ignorés dans les calculs.

        Args:
            array:           Tableau numpy à masquer (NDBI, NDVI, etc.)
            scl_path:        Chemin vers le fichier SCL Sentinel-2 (.tiff)
            invalid_classes: Tuple des classes SCL à masquer

        Returns:
            Tableau numpy de même dimension avec NaN sur les pixels nuageux.
        """
        try:
            with rasterio.open(scl_path) as scl_src:
                scl = scl_src.read(1)

                # Aligner le SCL si sa résolution diffère (SCL peut être à 20m)
                if scl.shape != array.shape:
                    logger.warning(
                        f"SCL {scl.shape} ≠ array {array.shape} → rééchantillonnage..."
                    )
                    scl_resampled = np.empty(array.shape, dtype=np.float32)
                    reproject(
                        source=rasterio.band(scl_src, 1),
                        destination=scl_resampled,
                        src_transform=scl_src.transform,
                        src_crs=scl_src.crs,
                        dst_transform=scl_src.transform,
                        dst_crs=scl_src.crs,
                        resampling=Resampling.nearest,  # Nearest pour données catégorielles
                    )
                    scl = scl_resampled.astype(int)

                invalid_mask = np.isin(scl, list(invalid_classes))
                masked = array.copy().astype(float)
                masked[invalid_mask] = np.nan

                n_masked = int(np.sum(invalid_mask))
                pct = 100.0 * n_masked / array.size
                logger.info(
                    f"Masque SCL (L6) — {n_masked:,} pixels masqués ({pct:.1f}%) "
                    f"classes={invalid_classes}"
                )
                return masked

        except FileNotFoundError:
            logger.warning(
                f"Fichier SCL introuvable : {scl_path}. "
                f"Masque non appliqué — résultats potentiellement bruités."
            )
            return array.copy().astype(float)

        except Exception as e:
            logger.error(f"Erreur application masque SCL: {str(e)}")
            return array.copy().astype(float)

    # ─────────────────────────────────────────────────────────────────────
    # SCORE DE CONFIANCE DYNAMIQUE — L5
    # ─────────────────────────────────────────────────────────────────────
    def compute_confidence(
        self,
        ndbi_t1: float,
        ndbi_t2: float,
        bsi: Optional[float] = None,
        surface_px: int = 1,
        cloud_cover_pct: float = 0.0,
    ) -> float:
        """
        Calcule un score de confiance dynamique pour une détection individuelle.

        Score composé de 4 facteurs pondérés :
          40% — Amplitude du saut NDBI (T1→T2)
          20% — Confirmation BSI (terrassement préalable visible)
          20% — Surface de la région détectée
          20% — Absence de nuages sur l'image source

        Args:
            ndbi_t1:         Valeur NDBI au centroïd en T1
            ndbi_t2:         Valeur NDBI au centroïd en T2
            bsi:             Valeur BSI au centroïd (ou None si non calculé)
            surface_px:      Surface en pixels de la région
            cloud_cover_pct: Pourcentage de nuages de l'image (0-100)

        Returns:
            Score float dans [0.0, 1.0].
        """
        score = 0.0

        # 40% — Amplitude du saut NDBI
        delta_ndbi = ndbi_t2 - ndbi_t1
        score += min(max(delta_ndbi / 0.4, 0.0), 1.0) * 0.40

        # 20% — BSI confirme terrassement
        if bsi is not None and bsi > 0.15:
            score += 0.20

        # 20% — Surface suffisante (2 pixels = ~200m² ou 20 pixels = ~2000m² idéal)
        score += min(surface_px / 20.0, 1.0) * 0.20

        # 20% — Couverture nuageuse faible
        score += (1.0 - min(cloud_cover_pct / 100.0, 1.0)) * 0.20

        return round(min(score, 1.0), 2)

    # ─────────────────────────────────────────────────────────────────────
    # METADATA DU RASTER
    # ─────────────────────────────────────────────────────────────────────
    def get_raster_transform(self, raster_path: str):
        """Retourne le transform affine d'un raster (pour conversion pixel → WGS84)."""
        with rasterio.open(raster_path) as src:
            return src.transform, src.crs, src.bounds

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
            resampling=Resampling.bilinear,
        )
        return resampled

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_cloud_percentage(scl_path: str) -> float:
        """
        Calcule le pourcentage de pixels nuageux depuis une carte SCL Sentinel-2.
        Utilisé pour la sélection automatique d'image (L6).

        Args:
            scl_path: Chemin vers le fichier SCL Sentinel-2 (.tiff)

        Returns:
            Pourcentage de pixels nuageux (classes 8, 9, 10) — float [0, 100].
        """
        try:
            with rasterio.open(scl_path) as src:
                scl = src.read(1)
            cloud_pixels = np.isin(scl, [8, 9, 10]).sum()
            return round(100.0 * cloud_pixels / scl.size, 2)
        except FileNotFoundError:
            logger.warning(f"SCL introuvable pour calcul nuages : {scl_path}")
            return 0.0
        except Exception as e:
            logger.error(f"Erreur get_cloud_percentage: {e}")
            return 0.0


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
