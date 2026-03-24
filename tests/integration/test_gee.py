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

print("\n=== TEST GOOGLE EARTH ENGINE (Phase 4) ===")
from module1_urbanisme.pipeline.gee_composite import GEECompositor
gee = GEECompositor()
gee_status = gee.status()
print(f"Status GEE: {gee_status}")
if gee_status.get("initialized"):
    print("✅ SUCCÈS : GEE est prêt à être utilisé !")
else:
    print("⚠️ GEE n'est pas complètement authentifié.")
