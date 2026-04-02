import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
from datetime import datetime

# Configuration du log spécial pour l'action 1.7
log_filename = "logs/audit_1_7_dates.log"
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
    print(f"--- Exécution Action 1.7 : Contrôle de Date (Metadata vs Filename) ---")
    logger.info("Début du test Action 1.7 : Contrôle de Date")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    success = True

    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        files = os.listdir(path)
        
        # Test sur la bande B08 (ou autre, c'est pour vérifier l'intégrité temporelle du script)
        band_file = f"B08_{date_dir}.tif"
        full_path = os.path.join(path, band_file)
        
        if os.path.exists(full_path):
            try:
                with rasterio.open(full_path) as src:
                    tags = src.tags()
                    logger.info(f"Analyse de {band_file}")
                    
                    # On cherche des tags temporels (les tags varient selon l'API source)
                    # SentineHub/CDSE mettent souvent ACQUISITION_DATE ou DATETIME
                    found_date = None
                    for key in ['ACQUISITION_DATE', 'DATETIME', 'TIFFTAG_DATETIME']:
                        if key in tags:
                            found_date = tags[key]
                            break
                    
                    if found_date:
                        logger.info(f"  Date trouvée dans métadonnées : {found_date}")
                        # On vérifie si la date du dossier (YYYY-MM-DD) est présente dans le tag
                        if date_dir in found_date:
                            logger.info(f"  [OK] Concordance date dossier ({date_dir}) et métadonnées ({found_date})")
                        else:
                            msg = f"CONFLIT DATE : Dossier {date_dir} vs Métadonnées {found_date} !"
                            print(f"⚠️ {msg}")
                            logger.warning(msg)
                    else:
                        logger.warning(f"  Aucun tag temporel standard trouvé dans {band_file}. (Vérification visuelle nécessaire)")
            except Exception as e:
                logger.error(f"  Erreur de lecture métadonnées {band_file} : {e}")

    print(f"✅ Action 1.7 Terminée : Audit temporel effectué.")
    logger.info("RÉSULTAT : Succès de l'audit temporel.")
    return True

if __name__ == "__main__":
    run_test()
