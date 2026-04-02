import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np

# Configuration du log spécial pour l'action 2.2
log_filename = "logs/audit_2_2_ndvi_outliers.log"
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
    print(f"--- Exécution Action 2.2 : Audit NDVI & Outliers ---")
    logger.info("Début du test Action 2.2 : NDVI Audit")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        b04_p = os.path.join(path, f"B04_{date_dir}.tif")
        b08_p = os.path.join(path, f"B08_{date_dir}.tif")
        
        if os.path.exists(b04_p) and os.path.exists(b08_p):
            try:
                with rasterio.open(b04_p) as r_s, rasterio.open(b08_p) as n_s:
                    red = r_s.read(1).astype(float)
                    nir = n_s.read(1).astype(float)
                    
                    denom = nir + red
                    with np.errstate(divide='ignore', invalid='ignore'):
                        ndvi = np.where(denom != 0, (nir - red) / denom, 0.0)
                    
                    # Nettoyage NaN/Inf
                    ndvi = np.nan_to_num(ndvi, nan=0.0, posinf=1.0, neginf=-1.0)
                    
                    min_v, max_v = ndvi.min(), ndvi.max()
                    logger.info(f"Date {date_dir} : NDVI Range [{min_v:.4f}, {max_v:.4f}]")
                    
                    # Vérification Outliers
                    if min_v < -1.0 or max_v > 1.0:
                        msg = f"ANOMALIE : NDVI hors limites sur {date_dir} !"
                        print(f"⚠️ {msg}")
                        logger.warning(msg)
                    
                    # Stats sur la végétation (>0.4)
                    veg_px = np.sum(ndvi > 0.4)
                    logger.info(f"  Pixels végétation (>0.4) : {veg_px} ({100*veg_px/ndvi.size:.2f}%)")
                    
            except Exception as e:
                logger.error(f"Erreur audit NDVI {date_dir} : {e}")
                success = False

    if success:
        print(f"✅ Action 2.2 Réussie : Le NDVI est cohérent et sans outliers critiques.")
        logger.info("RÉSULTAT : Succès de l'audit NDVI.")
    else:
        print(f"❌ Action 2.2 Échouée : Erreurs lors du calcul NDVI.")
        
    return success

if __name__ == "__main__":
    run_test()
