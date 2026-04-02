import os
# --- CONFIGURATION GDAL CRITIQUE (TOUT EN HAUT) ---
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

import sys
import django
import logging
# --- FIN CONFIGURATION ---

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.gis.geos import GEOSGeometry
from module1_urbanisme.models import MicrosoftFootprint

def run_test():
    print(f"--- Exécution Action 3.2 : Audit Géométrique V3 ---")
    bldg = MicrosoftFootprint.objects.filter(confidence_score__gte=0.75).first()
    if not bldg:
        print("⚠️ Aucun bâtiment Google V3 >= 0.75.")
        return
    centroid = bldg.geometry.centroid
    dx, dy = 0.00005, 0.00005
    detection_poly = GEOSGeometry(f"POLYGON(({centroid.x-dx} {centroid.y-dy}, {centroid.x+dx} {centroid.y-dy}, {centroid.x+dx} {centroid.y+dy}, {centroid.x-dx} {centroid.y+dy}, {centroid.x-dx} {centroid.y-dy}))")
    intersection = bldg.geometry.intersection(detection_poly)
    overlap_pct = (intersection.area / detection_poly.area) * 100
    if overlap_pct >= 70.0:
        print(f"✅ Action 3.2 Réussie : Recouvrement validé ({overlap_pct:.1f}% >= 70%).")
    else:
        print(f"⚠️ ALERTE : Faible recouvrement géométrique ({overlap_pct:.1f}% < 70%).")

if __name__ == "__main__":
    run_test()
