"""
Module d'Analyse Radar à Synthèse d'Ouverture (SAR) - Sentinel-1
CIV-Eye - Phase 7 : Détection Anti-Nuage (Data Fusion)

Ce module exploite les ondes radar qui traversent la couverture nuageuse 
pour confirmer la construction de bâtiments avec Google Earth Engine.
L'apparition d'un bâtiment (murs/métal) provoque une hausse de la 
rétrodiffusion VV (Delta VV dB positif).
"""

import logging
import os
import io
import requests
import numpy as np
import rasterio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Seuil de détection radar (historique)
THRESHOLD_VV = 0.15 

def init_gee():
    """Initialise Google Earth Engine via le projet Cloud"""
    try:
        import ee
        project_id = os.getenv("GEE_PROJECT_ID", "apt-momentum-490804-r7").strip()
        ee.Initialize(project=project_id)
        return ee
    except Exception as e:
        logger.error(f"Erreur d'initialisation GEE (SAR) : {e}")
        return None

def fetch_sar_median_array(ee_instance, region, target_date_str, window_days=15):
    """Télécharge la médiane SAR VV autour d'une date via GEE"""
    import ee
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    start = (dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
    end = (dt + timedelta(days=window_days)).strftime("%Y-%m-%d")
    
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .select(['VV'])
    )
    
    # Préférer l'orbite DESCENDING pour être cohérent.
    desc_col = collection.filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
    if desc_col.size().getInfo() > 0:
        collection = desc_col
    else:
        # Fallback ASCENDING si pas d'image
        collection = collection.filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
        
    if collection.size().getInfo() == 0:
        logger.warning(f"Aucune image radar trouvée entre {start} et {end}.")
        return None
        
    # Calcul temporel de la médiane = suppression 100% du Speckle (bruit radar gratuit)
    median_img = collection.median().clip(region)
    url = median_img.getDownloadURL({
        "scale": 10,  # Résolution 10m pour alignement avec Optique
        "crs": "EPSG:4326",
        "region": region,
        "format": "GEO_TIFF"
    })
    
    resp = requests.get(url)
    resp.raise_for_status()
    
    with rasterio.open(io.BytesIO(resp.content)) as src:
        arr = src.read(1).astype(np.float32)
    return arr

def fetch_and_evaluate_sar_for_bbox(sh_config, bbox_wgs84, date_t1, date_t2):
    """
    Télécharge les images Radar T1 et T2, nettoie le bruit, et retourne 
    la matrice de changement VV en dB prête pour la Data Fusion.
    Remplace l'ancienne dépendance coûteuse à Sentinel Hub.
    """
    import ee
    
    if bbox_wgs84 == "TREICHVILLE":
        bbox_wgs84 = [-4.03001, 5.28501, -3.97301, 5.32053]
        
    ee_instance = init_gee()
    if not ee_instance:
         return {"sar_detected": False, "delta_vv_db": None, "message": "Erreur GEE. Radar ignoré."}
         
    region = ee.Geometry.Rectangle(bbox_wgs84)
    
    logger.info(f"🛰️ Téléchargement Radar GEE (+Median Speckle Filter) de T1 : {date_t1}...")
    arr_t1 = fetch_sar_median_array(ee_instance, region, str(date_t1))
    
    logger.info(f"🛰️ Téléchargement Radar GEE (+Median Speckle Filter) de T2 : {date_t2}...")
    arr_t2 = fetch_sar_median_array(ee_instance, region, str(date_t2))
    
    if arr_t1 is None or arr_t2 is None:
        return {"sar_detected": False, "delta_vv_db": None, "message": "Données Radar insuffisantes ou dates hors limites."}
        
    # S'assurer que les tableaux ont une taille identique (différence de grille GEE S1/S2 potentielle d'un pixel)
    min_row = min(arr_t1.shape[0], arr_t2.shape[0])
    min_col = min(arr_t1.shape[1], arr_t2.shape[1])
    arr_t1 = arr_t1[:min_row, :min_col]
    arr_t2 = arr_t2[:min_row, :min_col]
    
    # ── LOGIQUE ──
    # Delta positif = Nouveau volume/métal/mur
    delta_vv_db = arr_t2 - arr_t1
    
    # Remplacer les NaN (bordures, erreurs de grille) par 0 dB de changement
    delta_vv_db = np.nan_to_num(delta_vv_db, nan=0.0)
    
    return {
        "sar_detected": True,
        "delta_vv_db": delta_vv_db,
        "message": f"Radar SAR fusionné et nettoyé avec succès ! (Δ VV Max = {delta_vv_db.max():.2f} dB)"
    }

def merge_optical_and_sar_masks(optical_mask: np.ndarray, sar_mask: np.ndarray) -> np.ndarray:
    """ Fonction de compatibilité historique (sera surchargée par la data-fusion du main) """
    return optical_mask
