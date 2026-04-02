import os
if os.name == "nt":
    os.environ["PATH"] = r"C:\Program Files\PostgreSQL\16\bin" + os.pathsep + os.environ.get("PATH", "")
    os.environ["GDAL_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgdal-34.dll")
    os.environ["GEOS_LIBRARY_PATH"] = os.path.join(r"C:\Program Files\PostgreSQL\16\bin", "libgeos_c.dll")

import os
import logging
import requests
import pystac_client
from datetime import datetime

# Configuration du log spécial pour l'action 1.5
log_filename = "logs/audit_1_5_cloud_timeout.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=log_filename,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def test_api_connection(url, timeout_val=5):
    """Teste la connexion à une URL avec un timeout spécifique."""
    logger.info(f"Test de connexion vers : {url} (timeout={timeout_val}s)")
    try:
        response = requests.get(url, timeout=timeout_val)
        if response.status_code == 200:
            logger.info(f"  [OK] Connexion réussie (Status 200)")
            return True
        else:
            logger.warning(f"  [!] Réponse inattendue : {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        logger.error(f"  [FAIL] Timeout atteint ({timeout_val}s)")
        return False
    except Exception as e:
        logger.error(f"  [FAIL] Erreur de connexion : {e}")
        return False

def run_test():
    print(f"--- Exécution Action 1.5 : Test de Lecture Cloud / Timeout ---")
    
    # 1. Test CDSE STAC API
    urls = [
        "https://catalogue.dataspace.copernicus.eu/stac",
        "https://planetarycomputer.microsoft.com/api/stac/v1"
    ]
    
    overall_success = True
    for url in urls:
        success = test_api_connection(url)
        if not success:
            print(f"⚠️ Problème de connexion ou latence élevée vers {url}")
            overall_success = False
            
    # 2. Simulation de Timeout (Test de la robustesse locale)
    # On va tenter d'ouvrir le catalogue avec un timeout de 0.001s pour forcer l'erreur et voir si elle est captée
    msg = "Simulation forcée de Timeout sur pystac_client..."
    print(f"ℹ️ {msg}")
    logger.info(msg)
    try:
        # pystac_client Client.open n'accepte pas directement timeout dans tous les environnements, 
        # mais on peut tester la réaction du code à une exception.
        import requests
        from pystac_client import Client
        
        # On force un timeout via requests directement pour voir le comportement
        requests.get("https://google.com", timeout=0.00001)
    except requests.exceptions.Timeout:
        logger.info("  [OK] L'exception Timeout est correctement soulevée par le système.")
    except Exception as e:
        logger.warning(f"  Autre exception : {e}")

    if overall_success:
        print(f"✅ Action 1.5 Terminée : Connexion aux APIs de données OK.")
        logger.info("RÉSULTAT : Succès de l'audit de connexion Cloud.")
    else:
        print(f"⚠️ Action 1.5 Terminée avec des avertissements (Lenteur ou API Injognable).")

    return overall_success

if __name__ == "__main__":
    run_test()
