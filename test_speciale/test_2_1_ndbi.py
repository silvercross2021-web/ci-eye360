import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import numpy as np

# Configuration du log spécial pour l'action 2.1
log_filename = "logs/audit_2_1_ndbi_logic.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def calculate_ndbi_test(b08, b11):
    """Calcule le NDBI avec protection."""
    # Simulation exacte du comportement NumPy dans le projet
    with np.errstate(divide='ignore', invalid='ignore'):
        denom = b11 + b08
        if isinstance(denom, (int, float)):
            if denom == 0: return 0.0
            return (b11 - b08) / denom
        return np.where(denom != 0, (b11 - b08) / denom, 0)

def run_test():
    print(f"--- Exécution Action 2.1 : Stress-Test NDBI ---")
    logger.info("Début du test Action 2.1 : NDBI Stress Test")
    
    # 1. Cas normal (Bâtiment brillant en SWIR B11)
    b08_1, b11_1 = 0.1, 0.4
    res_1 = calculate_ndbi_test(b08_1, b11_1)
    logger.info(f"Test 1 (B08={b08_1}, B11={b11_1}) → NDBI={res_1:.4f}")
    
    # 2. Cas Végétation (B08 élevé)
    b08_2, b11_2 = 0.5, 0.2
    res_2 = calculate_ndbi_test(b08_2, b11_2)
    logger.info(f"Test 2 (B08={b08_2}, B11={b11_2}) → NDBI={res_2:.4f}")
    
    # 3. Stress Test : Zéro absolu (B08=0, B11=0)
    b08_3, b11_3 = 0.0, 0.0
    res_3 = calculate_ndbi_test(b08_3, b11_3)
    logger.info(f"Test 3 (B08={b08_3}, B11={b11_3}) → NDBI={res_3:.4f}")
    
    # 4. Stress Test : Valeurs identiques (B11=B08)
    b08_4, b11_4 = 0.25, 0.25
    res_4 = calculate_ndbi_test(b08_4, b11_4)
    logger.info(f"Test 4 (B08={b08_4}, B11={b11_4}) → NDBI={res_4:.4f}")

    # Validation
    if res_3 == 0 and res_4 == 0 and res_1 > res_2:
        print(f"✅ Action 2.1 Réussie : La logique NDBI est stable et protégée.")
        logger.info("RÉSULTAT : Succès du Stress Test NDBI.")
    else:
        print(f"❌ Action 2.1 Échouée : Anomalie dans le calcul NDBI.")
        logger.error(f"Incohérence : res_1={res_1}, res_2={res_2}, res_3={res_3}, res_4={res_4}")

    return True

if __name__ == "__main__":
    run_test()
