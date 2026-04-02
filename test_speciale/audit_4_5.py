import os
import django
import sys
import numpy as np

if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator

def run_audit():
    print("--- Exécution Action 4.5 : Stress-test Taille L4 ---")
    calc = NDBICalculator()
    mask1 = np.zeros((10, 10), dtype=bool); mask1[1, 1] = True
    regions1 = calc.extract_change_regions(mask1, min_size=2, max_size=500)
    mask2 = np.zeros((10, 10), dtype=bool); mask2[1:3, 1:6] = True # 10 px
    regions2 = calc.extract_change_regions(mask2, min_size=2, max_size=500)
    mask3 = np.ones((30, 30), dtype=bool) # 900 px
    regions3 = calc.extract_change_regions(mask3, min_size=2, max_size=500)
    if len(regions1) == 0 and len(regions2) == 1 and len(regions3) == 0:
        print("✅ Action 4.5 Réussie : Les filtres de taille sont opérationnels.")
    else:
        print("❌ Action 4.5 Échouée.")

if __name__ == "__main__":
    run_audit()
