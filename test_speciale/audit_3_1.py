import os
# --- CONFIGURATION GDAL CRITIQUE (TOUT EN HAUT) ---
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

import sys
import django
# --- FIN CONFIGURATION ---

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from module1_urbanisme.models import MicrosoftFootprint
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_test():
    print("--- Exécution Action 3.1 : Test Intersection V3 (Google) ---")
    bldg = MicrosoftFootprint.objects.filter(confidence_score__gte=0.75).first()
    if not bldg:
        print("⚠️ Aucun bâtiment Google V3 >= 0.75.")
        return
    verifier = Verification4Couches()
    res = verifier.verify_detection(bldg.geometry.json, 0.1, 0.4, surface_m2=300)
    if res is None:
        print("✅ Action 3.1 Réussie : Le bâtiment pré-existant a été correctement filtré.")
    else:
        print(f"❌ Action 3.1 Échouée : Verdict={res.get('status')}")

if __name__ == "__main__":
    run_test()
