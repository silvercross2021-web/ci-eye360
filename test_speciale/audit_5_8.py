import os, django, sys
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from module1_urbanisme.models import MicrosoftFootprint
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.8 : Audit Alerte Orange Modification ---")
    bldg = MicrosoftFootprint.objects.filter(confidence_score__gte=0.85).first()
    if not bldg: print("⚠️ Aucun bâtiment Google V3 >= 0.85."); return
    verifier = Verification4Couches()
    res = verifier.verify_detection(bldg.geometry.json, 0.1, 0.45, change_type='new_construction', surface_m2=300)
    if res and res.get('alert_level') == 'orange' and 'MODIFICATION' in res.get('message').upper():
        print("✅ Action 5.8 Réussie : L'extension est en alerte Orange.")
    else: print(f"❌ Action 5.8 Échouée. {res}")

if __name__ == "__main__": run_audit()
