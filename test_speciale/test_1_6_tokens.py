import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
from dotenv import load_dotenv

# Configuration du log spécial pour l'action 1.6
log_filename = "logs/audit_1_6_tokens.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def run_test():
    load_dotenv()
    print(f"--- Exécution Action 1.6 : Test des Tokens & Credentials ---")
    logger.info("Début du test Action 1.6 : Test des Tokens")
    
    # 1. Vérification Sentinel Hub (Optionnel mais documenté)
    sh_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    sh_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    
    if sh_id and sh_secret:
        logger.info("[CONFIG] Sentinel Hub Credentials détectés.")
        print("ℹ️ Sentinel Hub Credits : OK (Détectés)")
    else:
        logger.warning("[FALLBACK] Sentinel Hub non configuré. Utilisation prévue de CDSE/PC.")
        print("⚠️ Sentinel Hub Credits : Manquants (Fallback activé)")

    # 2. Vérification CDSE (Optionnel car sans clé possible, mais on peut vérifier si une clé existe)
    cdse_token = os.getenv("CDSE_TOKEN")
    if cdse_token:
        logger.info("[CONFIG] CDSE Token existant (Prioritaire)")
        print("ℹ️ CDSE Token : OK (Détecé)")
    else:
        logger.info("[ANONYMOUS] CDSE Token absent (Utilisation anonyme STAC)")
        print("ℹ️ CDSE Token : Absent (Mode Anonyme/Public)")

    # 3. Microsoft Planetary Computer
    pc_key = os.getenv("MICROSOFT_PC_API_KEY")
    if pc_key:
        logger.info("[CONFIG] Microsoft PC API Key présente.")
        print("ℹ️ Microsoft PC : OK (Détecté)")
    else:
        logger.info("[CONFIG] Microsoft PC API Key absente (Utilisation publique sans signature signée ou limitée)")
        print("⚠️ Microsoft PC : Sans clé")

    print(f"✅ Action 1.6 Terminée : Configuration environnementale validée.")
    logger.info("RÉSULTAT : Audit de configuration terminé.")
    return True

if __name__ == "__main__":
    run_test()
