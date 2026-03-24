import os
import django
import numpy as np
import rasterio

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from module1_urbanisme.models import ImageSatellite
from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
from module1_urbanisme.pipeline.ai_detector import AIDetector
from module1_urbanisme.management.commands.run_detection import Command

def diagnose():
    cmd = Command()
    # On reprend les 2 images du processus
    img_t1 = ImageSatellite.objects.get(date_acquisition="2024-02-15")
    img_t2 = ImageSatellite.objects.get(date_acquisition="2025-01-15")
    
    print(f"Audit spectral pour T1={img_t1.date_acquisition} et T2={img_t2.date_acquisition}")
    
    # Simuler le pipeline
    results = cmd.calculate_ai_pipeline(img_t1, img_t2)
    regions = cmd.extract_change_regions(results, min_region_size=2)
    
    constructions = [r for r in regions if r['change_type'] == 'new_construction']
    print(f"Nombre de candidats constructions trouvés : {len(constructions)}")
    
    for i, r in enumerate(constructions):
        print(f"\nCandidat #{i+1}:")
        print(f"  NDBI T1 : {r['ndbi_t1']:.3f}")
        print(f"  NDBI T2 : {r['ndbi_t2']:.3f}")
        print(f"  Confiance Initiale (NDBI) : {r['confidence']:.3f}")
        
    print("\n--- Diagnostic des seuils Couche 3 ---")
    # On regarde si ça passe : ndbi_t2 > 0.2 and ndbi_t1 <= 0.25
    for i, r in enumerate(constructions):
        t2_ok = r['ndbi_t2'] > 0.2
        t1_ok = r['ndbi_t1'] <= 0.25
        print(f"Candidat #{i+1} : T1_OK={t1_ok}, T2_OK={t2_ok} -> Final={'VALIDE' if t1_ok and t2_ok else 'REJETÉ'}")

if __name__ == "__main__":
    diagnose()
