import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np

# Configuration du log spécial pour l'action 2.3
log_filename = "logs/audit_2_3_water_ndbi.log"
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
    print(f"--- Exécution Action 2.3 : Audit Zone Eau (Lagune) ---")
    logger.info("Début du test Action 2.3 : Water Audit via NDBI")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        b08_p = os.path.join(path, f"B08_{date_dir}.tif")
        b11_p = os.path.join(path, f"B11_{date_dir}.tif")
        
        if os.path.exists(b08_p) and os.path.exists(b11_p):
            try:
                with rasterio.open(b08_p) as n_s, rasterio.open(b11_p) as s_s:
                    nir = n_s.read(1).astype(float)
                    swir = s_s.read(1).astype(float)
                    
                    # Aligner si besoin (B11 est 20m, B08 est 10m)
                    if swir.shape != nir.shape:
                        # On fait une extraction simple du milieu pour le test statistique rapide
                        # ou on utilise une zone connue pour être de l'eau.
                        # Treichville : le coin Sud-Ouest est souvent la lagune.
                        pass

                    denom = swir + nir
                    with np.errstate(divide='ignore', invalid='ignore'):
                        ndbi = np.where(denom != 0, (swir - nir) / denom, 0.0)
                    
                    # On cherche les pixels très bas (< -0.15)
                    water_mask = ndbi < -0.15
                    water_count = np.sum(water_mask)
                    logger.info(f"Date {date_dir} : {water_count} pixels d'eau détectés (NDBI < -0.15)")
                    
                    if water_count == 0:
                        msg = f"ALERTE : Aucun pixel d'eau détecté sur {date_dir}. Le seuil -0.15 est peut-être trop bas ou l'image est décalée."
                        print(f"⚠️ {msg}")
                        logger.warning(msg)
                    else:
                        pct = (water_count / ndbi.size) * 100
                        logger.info(f"  Proportion d'eau : {pct:.2f}%")
                        print(f"✅ Action 2.3 : Eau détectée ({pct:.1f}%) sur {date_dir}.")
                    
            except Exception as e:
                logger.error(f"Erreur audit Eau {date_dir} : {e}")
                success = False

    return success

if __name__ == "__main__":
    run_test()
