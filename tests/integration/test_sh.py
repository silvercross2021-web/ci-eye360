import os
import sys
from dotenv import load_dotenv

# Charge explicitement le .env
load_dotenv(r'c:\Users\silve\Desktop\SIADE_hackathon\.env')

sys.path.insert(0, r'c:\Users\silve\Desktop\SIADE_hackathon')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

print("=== TEST SENTINEL HUB (Phase 3) ===")
from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher
fetcher = SentinelDataFetcher()
status = fetcher.status()
print(f"Status Fetcher: {status}")

if status.get("sentinel_hub"):
    print("Test téléchargement d'une image test (10x10px)...")
    small_bbox = {"min_lon": -4.0, "min_lat": 5.3, "max_lon": -3.999, "max_lat": 5.301}
    bands = fetcher.get_bands_for_date("2024-01-29", bands=["B04", "B08"], bbox=small_bbox)
    if bands and "B04" in bands:
        print(f"✅ SUCCÈS Sentinel Hub ! Bande B04 téléchargée, taille: {bands['B04'].shape}")
    else:
        print("❌ Échec téléchargement Sentinel Hub")
else:
    print("❌ Sentinel Hub non détecté comme actif.")
