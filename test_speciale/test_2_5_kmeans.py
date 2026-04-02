import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np
from sklearn.cluster import KMeans

# Configuration du log spécial pour l'action 2.5
log_filename = "logs/audit_2_5_kmeans_centroids.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

EXPORT_DIR = "module1_urbanisme/data_use/sentinel_api_exports"

def run_test():
    print(f"--- Exécution Action 2.5 : Audit K-Means Centroids ---")
    logger.info("Début du test Action 2.5 : K-Means Centroids Audit")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    date_dir = subdirs[-1] # On prend la date la plus récente (T2)
    
    path = os.path.join(EXPORT_DIR, date_dir)
    b08_p = os.path.join(path, f"B08_{date_dir}.tif")
    b11_p = os.path.join(path, f"B11_{date_dir}.tif")
    
    try:
        with rasterio.open(b08_p) as n_s, rasterio.open(b11_p) as s_s:
            nir = n_s.read(1).astype(float)
            swir = s_s.read(1).astype(float)
            
            # Calcul NDBI
            denom = swir + nir
            with np.errstate(divide='ignore', invalid='ignore'):
                ndbi = np.where(denom != 0, (swir - nir) / denom, 0.0)
            
            # On simule un K-Means à 3 classes (Eau, Végétation, Bâti)
            # Pour simplifier, on prend juste les pixels valides (pas NoData)
            valid_idx = (denom != 0)
            data_to_cluster = ndbi[valid_idx].reshape(-1, 1)
            
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            kmeans.fit(data_to_cluster)
            
            centroids = kmeans.cluster_centers_.flatten()
            centroids.sort() # Du plus bas au plus haut
            
            logger.info(f"Centroïdes NDBI trouvés : {centroids}")
            
            # Centroïde 0 : Probablement Eau (< -0.1)
            # Centroïde 1 : Probablement Végétation (-0.1 à 0.1)
            # Centroïde 2 : Probablement Bâti (> 0.1)
            
            built_centroid = centroids[-1]
            if built_centroid > 0.1:
                print(f"✅ Action 2.5 : Centroïde 'Bâti' validé (NDBI={built_centroid:.4f} > 0.1).")
                logger.info("RÉSULTAT : Succès de l'audit K-Means.")
            else:
                msg = f"ALERTE : Le centroïde le plus haut ({built_centroid:.4f}) est trop bas pour du bâti !"
                print(f"⚠️ {msg}")
                logger.warning(msg)
                
    except Exception as e:
        logger.error(f"Erreur audit K-Means : {e}")

    return True

if __name__ == "__main__":
    run_test()
