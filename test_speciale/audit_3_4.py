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

from module1_urbanisme.models import MicrosoftFootprint

def run_audit():
    print("--- Exécution Action 3.4 : Audit de Retrait Microsoft ---")
    count_with_score = MicrosoftFootprint.objects.filter(confidence_score__isnull=False).count()
    total = MicrosoftFootprint.objects.count()
    print(f"Nombre de bâtiments avec score Google : {count_with_score} / {total}")
    if count_with_score == total and total > 0:
        print("✅ Action 3.4 Réussie : Les données sont confirmées comme étant du Google V3.")
    else:
        print("⚠️ ALERTE : Présence de données anormales.")

if __name__ == "__main__":
    run_audit()
