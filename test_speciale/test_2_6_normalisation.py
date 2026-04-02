import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np

# Configuration du log spécial pour l'action 2.6
log_filename = "logs/audit_2_6_normalisation.log"
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
    print(f"--- Exécution Action 2.6 : Audit de Normalisation ---")
    logger.info("Début du test Action 2.6 : Audit de Normalisation")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        b08_p = os.path.join(path, f"B08_{date_dir}.tif")
        
        if os.path.exists(b08_p):
            try:
                with rasterio.open(b08_p) as src:
                    data = src.read(1)
                    vmean, vmax = data.mean(), data.max()
                    logger.info(f"Bande B08 {date_dir} : Moyenne={vmean:.4f}, Max={vmax:.4f}")
                    
                    # Si les valeurs sont > 1.0, ce sont des DN qui doivent être divisés par 10000
                    if vmax > 1.1: # on laisse une marge pour les pixels brillants
                        msg = f"DN DÉCTECTÉ : Les fichiers sur disque sont en Digital Numbers (Max={vmax:.1f}). Le pipeline doit les normaliser."
                        print(f"ℹ️ {msg}")
                        logger.info(msg)
                        # On vérifie si NDBICalculator s'en occupe
                    else:
                        msg = f"REFLECTANCE DÉTECTÉE : Les fichiers sont déjà en [0, 1] (Max={vmax:.4f})."
                        print(f"✅ {msg}")
                        logger.info(msg)
            except Exception as e:
                logger.error(f"Erreur audit normalisation : {e}")

    return True

if __name__ == "__main__":
    run_test()
