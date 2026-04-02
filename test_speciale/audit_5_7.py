import os, django, sys
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.7 : Audit Alerte Veille ---")
    verifier = Verification4Couches()
    res = verifier.verify_detection('{"type":"Point","coordinates":[-4,5.3]}', 0.1, 0.2, change_type='soil_activity', surface_m2=300)
    if res and res.get('alert_level') == 'veille':
        print("✅ Action 5.7 Réussie : Terrassement classé en Alerte 'Veille'.")
    else: print(f"❌ Action 5.7 Échouée. {res}")

if __name__ == "__main__": run_audit()
