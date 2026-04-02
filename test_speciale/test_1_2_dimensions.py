import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio

# Configuration du log spécial pour l'action 1.2
log_filename = "logs/audit_1_2_dimensions.log"
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
    print(f"--- Exécution Action 1.1 : Audit des Dimensions ---")
    logger.info("Début du test Action 1.2 : Audit des Dimensions")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    dimensions = {}
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        files = os.listdir(path)
        
        for band_base in ['B04', 'B08', 'B11']: # SCL peut varier en pixels si téléchargé ailleurs, mais doit être pareil ici
            band_file = f"{band_base}_{date_dir}.tif"
            full_path = os.path.join(path, band_file)
            
            if os.path.exists(full_path):
                try:
                    with rasterio.open(full_path) as src:
                        w, h = src.width, src.height
                        logger.info(f"Bande {band_file} : {w}x{h} px")
                        
                        if not dimensions:
                            dimensions = (w, h)
                            logger.info(f"Dimensions de référence fixées à : {w}x{h}")
                        elif (w, h) != dimensions:
                            msg = f"CONFLIT : La bande {band_file} a des dimensions {w}x{h} au lieu de {dimensions}"
                            print(f"❌ {msg}")
                            logger.error(msg)
                            success = False
                except Exception as e:
                    msg = f"ERREUR de lecture sur {band_file} : {e}"
                    print(f"❌ {msg}")
                    logger.error(msg)
                    success = False
            else:
                logger.warning(f"Fichier manquant ignoré dans ce test : {band_file}")

    if success:
        print(f"✅ Action 1.2 Réussie : Toutes les images ont des dimensions identiques ({dimensions[0]}x{dimensions[1]}).")
        logger.info("RÉSULTAT : Succès de l'audit des dimensions.")
    else:
        print(f"❌ Action 1.2 Échouée : Incohérence dans la taille des images.")
        logger.error("RÉSULTAT : Échec de l'audit des dimensions.")
        
    return success

if __name__ == "__main__":
    run_test()
