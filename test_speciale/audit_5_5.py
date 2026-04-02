import os, django, sys
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.5 : Test Hors Cadastre ---")
    verifier = Verification4Couches()
    res = verifier.verify_detection('{"type":"Point","coordinates":[0,0]}', 0.1, 0.45, surface_m2=300)
    if res.get('status') == 'sous_condition' and 'HORS PÉRIMÈTRE' in res.get('message').upper():
        print("✅ Action 5.5 Réussie : Détection hors cadastre signalée.")
    else: print(f"❌ Action 5.5 Échouée. {res}")

if __name__ == "__main__": run_audit()
