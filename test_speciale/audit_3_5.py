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

from django.contrib.gis.geos import Point
from module1_urbanisme.models import MicrosoftFootprint
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 3.5 : Audit Rayon de Recherche 15m ---")
    bldg = MicrosoftFootprint.objects.filter(confidence_score__gte=0.85).first()
    if not bldg:
        print("⚠️ Aucun bâtiment Google V3 >= 0.85.")
        return
    p = bldg.geometry.centroid
    d1 = 10 / 111111.0 
    p1 = Point(p.x + d1, p.y)
    verifier = Verification4Couches()
    res1 = verifier.verify_detection(p1.json, 0.1, 0.4, surface_m2=300)
    d2 = 25 / 111111.0
    p2 = Point(p.x + d2, p.y)
    res2 = verifier.verify_detection(p2.json, 0.1, 0.4, surface_m2=300)
    if res1 is None and res2 is not None:
        print("✅ Action 3.5 Réussie : Le rayon de 15m est PRECIS.")
    else:
        print(f"⚠️ ALERTE : Le rayon de 15m ne fonctionne pas comme prévu (Res1={res1}, Res2={res2})")

if __name__ == "__main__":
    run_audit()
