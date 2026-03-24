$ErrorActionPreference = "Stop"

Write-Host "1. Creation du venv 100% complet avec Heritage System..."
# On force l'heritage system pour avoir GDAL, GEOS, Numpy, Pillow depuis le systeme
python -m venv venv --system-site-packages

Write-Host "2. Mise a jour de PIP (Interne VENV)..."
.\venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "3. Installation des API pour la Phase 3 & 4 dans le VENV..."
# Oublions le requirements.txt complet pour éviter les recompilations C++.
# Les libs existantes (Django, GDAL, Numpy) sont déjà héritées !
.\venv\Scripts\python.exe -m pip install sentinelhub planetary-computer pystac-client earthengine-api oauthlib requests-oauthlib

Write-Host "`n=== SUCCES : VENV COMPLET CREE ==="
Write-Host "Pour l'utiliser, tape : .\venv\Scripts\activate"
