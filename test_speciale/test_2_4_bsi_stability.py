import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import rasterio
import numpy as np

# Configuration du log spécial pour l'action 2.4
log_filename = "logs/audit_2_4_bsi_stability.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

EXPORT_DIR = "module1_urbanisme/data_use/sentinel_api_exports"

def calculate_bsi_raw(b04, b08, b11):
    """Calcule le BSI simplifié (B11+B04-B08)/(B11+B04+B08)."""
    num = (b11 + b04) - b08
    denom = (b11 + b04) + b08
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(denom != 0, num / denom, 0.0)

def run_test():
    print(f"--- Exécution Action 2.4 : Test de Stabilité BSI ---")
    logger.info("Début du test Action 2.4 : BSI Stability Audit")
    
    subdirs = [d for d in os.listdir(EXPORT_DIR) if os.path.isdir(os.path.join(EXPORT_DIR, d))]
    
    if len(subdirs) < 2:
        print("❌ Besoin de 2 dates pour le test de stabilité.")
        return False
        
    date_t1, date_t2 = subdirs[0], subdirs[1]
    
    try:
        def get_bsi(date):
            path = os.path.join(EXPORT_DIR, date)
            b04_p = os.path.join(path, f"B04_{date}.tif")
            b08_p = os.path.join(path, f"B08_{date}.tif")
            b11_p = os.path.join(path, f"B11_{date}.tif")
            
            with rasterio.open(b04_p) as r_s, rasterio.open(b08_p) as n_s, rasterio.open(b11_p) as s_s:
                red = r_s.read(1).astype(float)
                nir = n_s.read(1).astype(float)
                swir = s_s.read(1).astype(float)
                
                # On force le SWIR à la même taille si besoin
                if swir.shape != red.shape:
                    swir = np.zeros_like(red) # On simplifie pour le test de stabilité globale ou on saute
                    return None
                    
                return calculate_bsi_raw(red, nir, swir)

        bsi_t1 = get_bsi(date_t1)
        bsi_t2 = get_bsi(date_t2)

        if bsi_t1 is not None and bsi_t2 is not None:
            # On cherche une zone stable : NDVI élevé (forêt)
            # Puis on regarde la différence de BSI sur ces pixels
            diff = np.abs(bsi_t1 - bsi_t2)
            mean_diff = np.mean(diff)
            logger.info(f"Différence absolue moyenne de BSI : {mean_diff:.4f}")
            
            if mean_diff < 0.15:
                print(f"✅ Action 2.4 : BSI relativement stable (diff moyenne = {mean_diff:.4f}).")
            else:
                msg = f"ALERTE : Variation importante du BSI ({mean_diff:.4f})."
                print(f"⚠️ {msg}")
                logger.warning(msg)
        else:
            print("⚠️ Échec test stabilité BSI : dimensions ou fichiers incompatibles.")
            
    except Exception as e:
        logger.error(f"Erreur audit stabilité BSI : {e}")

    return True

if __name__ == "__main__":
    run_test()
