import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
from datetime import datetime

# Configuration du log spécial pour l'action 1.1
log_filename = "logs/audit_1_1_inventory.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

EXPORT_DIR = "module1_urbanisme/data_use/sentinel_api_exports"
REQUIRED_BANDS = ['B04.tif', 'B08.tif', 'B11.tif', 'SCL.tif']

def run_test():
    print(f"--- Exécution Action 1.1 : Inventaire Spatial ---")
    logger.info("Début du test Action 1.1 : Inventaire Spatial")
    
    if not os.path.exists(EXPORT_DIR):
        msg = f"ERREUR CRITIQUE : Le dossier {EXPORT_DIR} est introuvable."
        print(f"❌ {msg}")
        logger.error(msg)
        return False

    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    logger.info(f"Dossiers de dates trouvés : {subdirs}")
    
    if len(subdirs) < 2:
        msg = f"ERREUR : Seulement {len(subdirs)} dossiers trouvés. Il en faut au moins 2 (T1 et T2)."
        print(f"❌ {msg}")
        logger.error(msg)
        return False

    success = True
    for date_dir in subdirs:
        path = os.path.join(EXPORT_DIR, date_dir)
        files = os.listdir(path)
        logger.info(f"Analyse du dossier : {date_dir}")
        
        for band_base in ['B04', 'B08', 'B11', 'SCL']:
            band_with_date = f"{band_base}_{date_dir}.tif"
            if band_with_date in files:
                logger.info(f"  [OK] Bande présente : {band_with_date}")
            else:
                msg = f"MANQUANT : La bande {band_with_date} est absente du dossier {date_dir}"
                print(f"⚠️ {msg}")
                logger.warning(msg)
                success = False
                
    if success:
        print(f"✅ Action 1.1 Réussie : Toutes les bandes sont présentes pour les dates détectées.")
        logger.info("RÉSULTAT : Succès total de l'inventaire.")
    else:
        print(f"❌ Action 1.1 Échouée : Des fichiers manquent sur le disque.")
        logger.error("RÉSULTAT : Échec de l'inventaire.")
        
    return success

if __name__ == "__main__":
    run_test()
