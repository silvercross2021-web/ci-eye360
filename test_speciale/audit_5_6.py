import os, django, sys
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.6 : Audit Confiance IA ---")
    verifier = Verification4Couches()
    res1 = verifier.verify_detection('{"type":"Point","coordinates":[-4,5]}', 0.05, 0.12, confidence_ia=0.5, surface_m2=300)
    res2 = verifier.verify_detection('{"type":"Point","coordinates":[-4,5]}', 0.05, 0.12, confidence_ia=0.95, surface_m2=300)
    if res1 is None and res2 is not None:
        print("✅ Action 5.6 Réussie : L'IA module les seuils.")
    else: print(f"❌ Action 5.6 Échouée. {res1}, {res2}")

if __name__ == "__main__": run_audit()
