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
    print("--- Exécution Action 5.3 : Test Faux Positif Berge ---")
    zone = ZoneCadastrale.objects.filter(zone_type__in=['water', 'flood_prone']).first()
    if not zone: print("⚠️ Aucune zone 'water' ou 'flood_prone' en base."); return
    verifier = Verification4Couches()
    res = verifier.verify_detection(zone.geometry.centroid.json, 0.05, 0.15, change_type='soil_activity', surface_m2=300)
    if res is None: print(f"✅ Action 5.3 Réussie : Le faux positif sur berge ({zone.zone_type}) est ignoré.")
    else: print(f"❌ Action 5.3 Échouée. {res}")

if __name__ == "__main__": run_audit()
