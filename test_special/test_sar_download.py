import os
import io
import time
import logging
import numpy as np
import rasterio
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# BBOX Treichville (même que dans les autres scripts)
TREICHVILLE_BBOX = [-4.03001, 5.28501, -3.97301, 5.32053]

def init_gee():
    """Initialise Google Earth Engine via le .env"""
    try:
        import ee
        project_id = os.getenv("GEE_PROJECT_ID", "apt-momentum-490804-r7").strip()
        logger.info(f"Initialisation de GEE avec le projet: {project_id}")
        ee.Initialize(project=project_id)
        return ee
    except Exception as e:
        logger.error(f"Erreur d'initialisation GEE : {e}")
        return None

def download_sar_median(ee, start_date, end_date, output_path):
    """
    Télécharge une image Sentinel-1 SAR (Radar) 100% GRATUITE,
    DÉJÀ ORTHORECTIFIÉE ET SANS BRUIT via une médiane temporelle.
    """
    logger.info(f"Début du traitement SAR pour la période: {start_date} -> {end_date}")
    
    # Zone de Treichville
    region = ee.Geometry.Rectangle(TREICHVILLE_BBOX)

    # 1. Requête de la collection COPERNICUS/S1_GRD (Déjà traitée par Google !)
    # On filtre sur 'IW' (Interferometric Wide) et on garde une seule orbite (ex: DESCENDING)
    # pour éviter de mélanger des images prises sous des angles différents (ce qui crée du flou radar).
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
        .select(['VV']) # 'VV' est la bande qui réagit très fort aux nouveaux bâtiments (Béton/Métal)
    )

    count = collection.size().getInfo()
    logger.info(f"Nombre d'images Sentinel-1 brutes trouvées dans cette période : {count}")
    
    if count == 0:
        logger.warning("Aucune image Sentinel-1 trouvée avec pass DESCENDING. Essai avec ASCENDING...")
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
            .select(['VV'])
        )
        count = collection.size().getInfo()
        logger.info(f"Nombre d'images Sentinel-1 (ASCENDING) trouvées : {count}")
        if count == 0:
            logger.error("Toujours aucune image trouvée. Période modifiée ?")
            return None

    # 2. LA MAGIE POUR ENLEVER LE BRUIT (SPECKLE) : La médiane temporelle
    # Au lieu de prendre 1 seule image (qui aura du bruit poivre et sel), 
    # on prend les ~4 ou 5 images du mois et on calcule la médiane de chaque pixel.
    # Résultat : Le bruit aléatoire disparait, mais les bâtiments (fixes) restent parfaitement nets !
    median_image = collection.median().clip(region)

    logger.info("Calcul de la médiane effectué sur les serveurs de Google.")
    logger.info("Début du téléchargement de l'image finale...")

    # 3. Téléchargement via l'API GEE
    try:
        url = median_image.getDownloadURL({
            "scale": 10, # Résolution 10 mètres (comme l'optique S2)
            "crs": "EPSG:4326",
            "region": region,
            "format": "GEO_TIFF"
        })
        
        response = requests.get(url)
        response.raise_for_status()

        # Enregistrer et relire pour s'assurer de sa validité
        with open(output_path, "wb") as f:
            f.write(response.content)
            
        with rasterio.open(output_path) as src:
            data = src.read(1)
            
        logger.info(f"✅ SUCCÈS : Image SAR téléchargée dans {output_path}")
        logger.info(f"    -> Shape : {data.shape}")
        logger.info(f"    -> Min (dB) : {data.min():.2f} // Max (dB) : {data.max():.2f}")
        logger.info("    (Note: un bâtiment récent aura généralement une valeur VV en dB plus élevée)")
        
        return output_path

    except Exception as e:
        logger.error(f"Erreur lors du téléchargement : {e}")
        return None

if __name__ == "__main__":
    ee = init_gee()
    if ee:
        # Création du dossier pour le test
        os.makedirs("test_special/outputs", exist_ok=True)
        
        # Test pour Janvier/Février 2024
        print("\n--- Test 1 : Période Janvier/Février 2024 ---")
        out_2024 = "test_special/outputs/SAR_VV_2024.tif"
        download_sar_median(ee, "2024-01-15", "2024-02-15", out_2024)
        
        # Test pour Janvier/Février 2025
        print("\n--- Test 2 : Période Janvier/Février 2025 ---")
        out_2025 = "test_special/outputs/SAR_VV_2025.tif"
        download_sar_median(ee, "2025-01-15", "2025-02-15", out_2025)
        
        print("\n✅ Terminé. Tu peux inspecter les images générées dans test_special/outputs/")
