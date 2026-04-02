import os
import django
import sys

# Setup GDAL/GEOS for Windows
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from module1_urbanisme.models import MicrosoftFootprint
from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches

def run_audit():
    print("--- Exécution Action 3.3 : Stress-Test Seuil Google ---")
    verifier = Verification4Couches()
    tests = [
        {"score": 0.30, "expected_ignore": True, "label": "Score Faible (0.3)"},
        {"score": 0.85, "expected_ignore": False, "label": "Score Élevé (0.85)"}
    ]
    for t in tests:
        print(f"Test de {t['label']}...")
        bldg = MicrosoftFootprint.objects.filter(confidence_score__gte=t['score']).order_by('confidence_score').first()
        if bldg:
            res = verifier.verify_detection(bldg.geometry.json, 0.1, 0.4, surface_m2=300)
            status = "REJETÉ (Correct)" if res is None else "ACCEPTÉ (Suspect)"
            print(f"  Resultat pour score {bldg.confidence_score}: {status}")
            if (t["expected_ignore"] and res is not None) or (not t["expected_ignore"] and res is None):
                 print(f"  ✅ Réussie : Comportement correct pour score {bldg.confidence_score}")
        else:
            print(f"  ⚠️ Pas de bâtiment trouvé avec score >= {t['score']}")

if __name__ == "__main__":
    run_audit()
