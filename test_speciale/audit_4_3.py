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

from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator

def run_audit():
    print("--- Exécution Action 4.3 : Test du Mouchard BSI ---")
    calc = NDBICalculator()
    score1 = calc.compute_confidence(ndbi_t1=0.1, ndbi_t2=0.4, bsi=0.2, surface_px=2)
    score2 = calc.compute_confidence(ndbi_t1=0.1, ndbi_t2=0.4, bsi=0.0, surface_px=2)
    if score1 > score2:
        print("✅ Action 4.3 Réussie : Le BSI apporte un bonus de confiance (0.20).")
    else:
        print("❌ Action 4.3 Échouée.")

if __name__ == "__main__":
    run_audit()
