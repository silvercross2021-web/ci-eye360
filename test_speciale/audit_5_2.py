import os, django, sys
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from module1_urbanisme.models import ZoneCadastrale
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.2 : Test Zone Sous Condition ---")
    zone = ZoneCadastrale.objects.filter(buildable_status='conditional').first()
    if not zone: print("⚠️ Aucune zone 'conditional' en base."); return
    verifier = Verification4Couches()
    res = verifier.verify_detection(zone.geometry.centroid.json, 0.1, 0.45, surface_m2=300)
    if res.get('status') == 'sous_condition' and res.get('alert_level') == 'orange':
        print("✅ Action 5.2 Réussie : Alerte Orange en zone conditionnelle.")
    else: print(f"❌ Action 5.2 Échouée. {res}")

if __name__ == "__main__": run_audit()
