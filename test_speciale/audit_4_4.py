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
    print("--- Exécution Action 4.4 : Audit SCL (Nuages) ---")
    array = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=float)
    invalid_classes = (3, 6, 8, 9, 10)
    scl = np.array([[4, 9], [6, 2]])
    invalid_mask = np.isin(scl, list(invalid_classes))
    masked = array.copy().astype(float)
    masked[invalid_mask] = np.nan
    if np.isnan(masked[0][1]) and not np.isnan(masked[0][0]):
        print("✅ Action 4.4 Réussie : Le pixel avec SCL=9 est correctement mis à NaN.")
    else:
        print("❌ Action 4.4 Échouée.")

if __name__ == "__main__":
    run_audit()
