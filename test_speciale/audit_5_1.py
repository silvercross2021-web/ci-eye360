import os
import django
import sys

if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from module1_urbanisme.models import ZoneCadastrale
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 5.1 : Test Zone Interdite ---")
    zone = ZoneCadastrale.objects.filter(buildable_status='forbidden').first()
    if not zone:
        print("⚠️ Aucune zone 'forbidden' en base.")
        return
    verifier = Verification4Couches()
    res = verifier.verify_detection(zone.geometry.centroid.json, 0.1, 0.45, surface_m2=300)
    if res.get('status') == 'infraction_zonage' and res.get('alert_level') == 'rouge':
        print("✅ Action 5.1 Réussie : Alerte rouge en zone interdite.")
    else:
        print("❌ Action 5.1 Échouée.")

if __name__ == "__main__":
    run_audit()
