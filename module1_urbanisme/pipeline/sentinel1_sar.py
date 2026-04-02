"""
Module d'Analyse Radar à Synthèse d'Ouverture (SAR) - Sentinel-1
CIV-Eye - Phase 7 : Détection Anti-Nuage (Cloud-Piercing)

Ce module exploite les ondes radar (polarisations VV et VH) 
qui traversent la couverture nuageuse pour confirmer la construction de bâtiments.
L'apparition d'un bâtiment (dièdre métallique/béton) provoque une forte augmentation
de la rétrodiffusion VV (Backscatter VV_T2 > VV_T1).
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

# Seuil de détection pour un nouveau bâtiment (habituellement > 2.0 à 4.0 dB)
# Dans ce contexte (valeurs linéaires ou normalisées), on ajuste un seuil empirique.
THRESHOLD_VV = 0.15 


def evaluate_sar_backscatter_delta(vv_t1: np.ndarray, vv_t2: np.ndarray, vh_t1: np.ndarray, vh_t2: np.ndarray) -> np.ndarray:
    
    # Calcul de la différence de rétrodiffusion VV entre T2 et T1
    delta_vv = vv_t2 - vv_t1
    # Masque binaire
    sar_mask = (delta_vv > THRESHOLD_VV).astype(np.uint8)
    
    logger.info(f"Analyse SAR exécutée. Pixels à forte rétrodiffusion (Delta VV) : {np.sum(sar_mask)}")
    return sar_mask


def fetch_and_evaluate_sar_for_bbox(sh_config, bbox_wgs84, date_t1, date_t2):
    """
    Fonction utilitaire pour s'interfacer avec Sentinel Hub API (Collection SENTINEL1_GRD).
    Récupère directement les données Orthorectifiées (Backscatter Coefficient Gamma0).
    """
    logger.info(f"Demande API Sentinel-1 GRD pour la zone {bbox_wgs84} sur {date_t1} -> {date_t2}")
    
    # NOTE: L'intégration réelle Sentinel Hub API SENTINEL1_GRD nécessite
    # les quotas API payants. Le workflow suivant est structuré pour s'intégrer
    # sans erreur dans la pipeline globale.
    
    return {
        "sar_detected": False, 
        "delta_vv_db": None,
        "message": "En attente du token d'entreprise Sentinel Hub pour les bandes S1-GRD."
    }

def merge_optical_and_sar_masks(optical_mask: np.ndarray, sar_mask: np.ndarray) -> np.ndarray:
    """
    Applique la Fusion de Données (Data Fusion) entre le masque optique Sentinel-2 (NDBI)
    et le masque Radar Sentinel-1 (VV).
    Si un pixel est nuageux en Optique, le SAR prend le relais (OU logique).
    Si les deux sont disponibles, l'un ou l'lautre confirme la construction.
    """
    if optical_mask.shape != sar_mask.shape:
        logger.warning("Redimensionnement requis pour la fusion SAR/S2.")
        import cv2
        sar_mask = cv2.resize(sar_mask, (optical_mask.shape[1], optical_mask.shape[0]), interpolation=cv2.INTER_NEAREST)
        
    fused_mask = np.logical_or(optical_mask > 0, sar_mask > 0).astype(np.uint8) * 255
    return fused_mask
