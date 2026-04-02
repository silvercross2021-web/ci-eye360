import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np
from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03

# Configuration du log spécial pour l'action 1.8
log_filename = "logs/audit_1_8_b03_synthesis.log"
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
    print(f"--- Exécution Action 1.8 : Test de Synthèse B03 (Vert) ---")
    logger.info("Début du test Action 1.8 : Synthèse B03")

    # On teste sur la première date trouvée
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    if not subdirs:
        print("❌ Aucun dossier de données pour tester la synthèse")
        return False
        
    date_dir = subdirs[0]
    path = os.path.join(EXPORT_DIR, date_dir)
    
    b04_p = os.path.join(path, f"B04_{date_dir}.tif")
    b08_p = os.path.join(path, f"B08_{date_dir}.tif")
    b03_out = os.path.join(path, f"B03_audit_test.tif")

    if os.path.exists(b04_p) and os.path.exists(b08_p):
        try:
            logger.info(f"Tentative de synthèse sur {date_dir}")
            res_path = synthesize_b03(b04_p, b08_p, b03_out)
            
            if res_path and os.path.exists(res_path):
                with rasterio.open(res_path) as src:
                    data = src.read(1)
                    vmean = data.mean()
                    logger.info(f"  [OK] B03 synthétisé. Moyenne={vmean:.4f}")
                    if vmean > 0:
                        print(f"✅ Action 1.8 Réussie : B03 synthétisé avec succès ({vmean:.4f} moy).")
                        # Nettoyage
                        os.remove(b03_out)
                    else:
                        print(f"⚠️ Action 1.8 : Image B03 synthétisée mais vide (moyenne 0).")
                        logger.warning("L'image synthétisée est vide.")
            else:
                print("❌ Échec : Le fichier de sortie n'a pas été généré.")
        except Exception as e:
            msg = f"ERREUR de synthèse B03 : {e}"
            print(f"❌ {msg}")
            logger.error(msg)
            return False
    else:
        print("❌ Bandes B04 ou B08 manquantes pour tester la synthèse.")
        return False

    return True

if __name__ == "__main__":
    run_test()
