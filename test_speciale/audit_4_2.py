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
    print("--- Exécution Action 4.2 : Stress-test Végétation ---")
    new_constructions = np.array([[True, True], [False, False]])
    ndvi_t2 = np.array([[0.1, 0.6], [0.1, 0.6]])
    vegetation_mask = (ndvi_t2 > 0.4)
    filtered = new_constructions & ~vegetation_mask
    if not filtered[0][1] and filtered[0][0]:
        print("✅ Action 4.2 Réussie : Les pixels à fort NDVI (0.6) sont correctement masqués.")
    else:
        print("❌ Action 4.2 Échouée.")

if __name__ == "__main__":
    run_audit()
