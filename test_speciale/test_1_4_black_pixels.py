import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np

# Configuration du log spécial pour l'action 1.4
log_filename = "logs/audit_1_4_black_pixels.log"
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
    print(f"--- Exécution Action 1.4 : Scanner de Pixels Noirs ---")
    logger.info("Début du test Action 1.4 : Scanner de Pixels Noirs")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
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
                        data = src.read(1)
                        total_px = data.size
                        zero_px = np.sum(data == 0)
                        pct_zero = (zero_px / total_px) * 100
                        
                        logger.info(f"Bande {band_file} : {zero_px} pixels à zéro ({pct_zero:.2f}%)")
                        
                        if pct_zero > 10.0:
                            msg = f"ALERTE : La bande {band_file} contient {pct_zero:.2f}% de pixels vides !"
                            print(f"⚠️ {msg}")
                            logger.warning(msg)
                            # On ne bloque pas forcément (échec=False) car une image au bord de tuile peut avoir 10% de noir
                        elif pct_zero > 50.0:
                            msg = f"CRITIQUE : {band_file} est à plus de 50% vide !"
                            print(f"❌ {msg}")
                            logger.error(msg)
                            success = False
                            
                except Exception as e:
                    msg = f"ERREUR de lecture sur {band_file} : {e}"
                    print(f"❌ {msg}")
                    logger.error(msg)
                    success = False

    if success:
        print(f"✅ Action 1.4 Terminée : Analyse des pixels noirs effectuée.")
        logger.info("RÉSULTAT : Succès de l'audit des pixels noirs.")
    else:
        print(f"❌ Action 1.4 Échouée : Trop de données manquantes (images vides).")
        logger.error("RÉSULTAT : Échec de l'audit des pixels noirs.")
        
    return success

if __name__ == "__main__":
    run_test()
