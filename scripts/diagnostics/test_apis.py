import os
import sys

# Assure qu'on est dans le bon dossier
sys.path.insert(0, r'c:\Users\silve\Desktop\SIADE_hackathon')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Contourner les appels de DB pour juste tester les API
import django
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

print("=== TEST SENTINEL HUB (Phase 3) ===")
try:
    from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher
    fetcher = SentinelDataFetcher()
    status = fetcher.status()
    print(f"Status Fetcher: {status}")
    
    if status.get("sentinel_hub"):
        print("Test téléchargement d'une image test (10x10px)...")
        # On va chercher un tout petit BBOX juste pour tester la clé
        small_bbox = {"min_lon": -4.0, "min_lat": 5.3, "max_lon": -3.999, "max_lat": 5.301}
        bands = fetcher.get_bands_for_date("2024-01-29", bands=["B04", "B08"], bbox=small_bbox)
        if bands and "B04" in bands:
            print(f"✅ SUCCÈS Sentinel Hub ! Bande B04 téléchargée, taille: {bands['B04'].shape}")
        else:
            print("❌ Échec téléchargement Sentinel Hub")
    else:
        print("❌ Sentinel Hub non détecté comme actif.")
except Exception as e:
    print(f"❌ Erreur test Sentinel Hub : {e}")

print("\n=== TEST GOOGLE EARTH ENGINE (Phase 4) ===")
try:
    from module1_urbanisme.pipeline.gee_composite import GEECompositor
    gee = GEECompositor()
    gee_status = gee.status()
    print(f"Status GEE: {gee_status}")
    if gee_status.get("initialized"):
        print("✅ SUCCÈS : GEE est prêt à être utilisé !")
    else:
        print("⚠️ GEE n'est pas complètement authentifié.")
except Exception as e:
    print(f"❌ Erreur test GEE : {e}")
