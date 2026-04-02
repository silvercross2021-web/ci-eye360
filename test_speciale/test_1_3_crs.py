import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio

# Configuration du log spécial pour l'action 1.3
log_filename = "logs/audit_1_3_crs.log"
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
    print(f"--- Exécution Action 1.3 : Audit de Projection (CRS) ---")
    logger.info("Début du test Action 1.3 : Audit de Projection")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    expected_crs = "EPSG:4326"
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        files = os.listdir(path)
        
        for band_base in ['B04', 'B08', 'B11']:
            band_file = f"{band_base}_{date_dir}.tif"
            full_path = os.path.join(path, band_file)
            
            if os.path.exists(full_path):
                try:
                    with rasterio.open(full_path) as src:
                        crs = str(src.crs).upper()
                        logger.info(f"Bande {band_file} : CRS={crs}")
                        
                        if src.crs.to_epsg() != 4326 and "WGS 84" not in str(src.crs):
                            msg = f"CONFLIT CRS : La bande {band_file} est en {src.crs} au lieu de EPSG:4326"
                            print(f"❌ {msg}")
                            logger.error(msg)
                            success = False
                except Exception as e:
                    msg = f"ERREUR de lecture sur {band_file} : {e}"
                    print(f"❌ {msg}")
                    logger.error(msg)
                    success = False

    if success:
        print(f"✅ Action 1.3 Réussie : Toutes les images sont en {expected_crs}.")
        logger.info("RÉSULTAT : Succès de l'audit CRS.")
    else:
        print(f"❌ Action 1.3 Échouée : Problème de projection (CRS).")
        logger.error("RÉSULTAT : Échec de l'audit CRS.")
        
    return success

if __name__ == "__main__":
    run_test()
