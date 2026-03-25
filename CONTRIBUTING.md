# CONTRIBUTING — Guide de Contribution CIV-EYE

Guide complet pour comprendre l'architecture du projet, développer les modules 2 et 3, et contribuer correctement. **À lire entièrement avant de commencer.**

---

## 1. État du projet et architecture globale

### Modules

| Module | Dossier | État |
|---|---|---|
| **Module 1 — Urbanisme** | `module1_urbanisme/` | Complet — 39 810 bâtiments, 729 détections, pipeline opérationnel |
| **Module 2 — Agroécologie** | `module2_agroecologie/` | Squelette Django vide — modèles et pipeline à créer |
| **Module 3 — Orpaillage** | `module3_orpaillage/` | Squelette Django vide — modèles et pipeline à créer |

### Fichiers partagés (modifier avec accord)

| Fichier | Impact |
|---|---|
| `config/settings.py` | Configuration globale Django (GDAL, PostGIS, INSTALLED_APPS) |
| `config/urls.py` | Routes de toute l'application |
| `requirements.txt` | Dépendances Python partagées |
| `templates/module1/base.html` | Thème "Cyber Tactique" dark mode — ne pas réécrire les variables `:root` CSS |

---

## 2. Architecture technique du Module 1 (référence pour M2 et M3)

Comprendre comment Module 1 fonctionne permet de reproduire le même pattern pour les autres modules.

### Modèles de données (`models.py`)

```python
# 4 modèles PostGIS dans module1_urbanisme/models.py

ZoneCadastrale           # 19 zones du plan d'urbanisme V10 de Treichville
                         # Champs : zone_id, name, zone_type, buildable_status, geometry (PolygonField)

ImageSatellite           # Images Sentinel-2 importées (2 dates : T1 et T2)
                         # Champs : date_acquisition, bands (JSONField = chemins TIF), classification_map (SCL)

MicrosoftFootprint       # 39 810 empreintes Google Open Buildings V3
                         # Champs : geometry (PolygonField), source, confidence_score
                         # Note : nom historique conservé pour compatibilité migrations

DetectionConstruction    # 729 détections géolocalisées avec statut
                         # Champs : zone_cadastrale (FK), geometry, ndbi_t1, ndbi_t2, status, alert_level
                         # status : infraction_zonage / sous_condition / conforme / surveillance_preventive
                         # alert_level : rouge / orange / vert / veille
```

### Pipeline de traitement (`pipeline/`)

Le pipeline Module 1 suit 5 étapes enchaînées dans `run_detection.py` :

```
Étape 1 — Acquisition des images
  sentinel_data_fetcher.py  →  Télécharge les bandes Sentinel-2 depuis CDSE/SH/GEE
  Format de sortie : fichiers TIF dans data_use/sentinel_api_exports/{date}/B04_{date}.tif, etc.

Étape 2 — Calcul des indices spectraux
  ndbi_calculator.py
    calculate_ndbi(b08_path, b11_path)           → NDBI = (B11-B08)/(B11+B08)
    calculate_bsi(b04_path, b08_path, b11_path)  → BSI = (B11+B04-B08)/(B11+B04+B08)
    calculate_ndvi(b04_path, b08_path)            → NDVI = (B08-B04)/(B08+B04)
    detect_changes(ndbi_t1, ndbi_t2, bsi, ndvi)  → masques new_constructions + soil_activity + demolished
    apply_scl_mask(array, scl_path)               → exclut nuages + eau (classes SCL 3,6,8,9,10)

Étape 3 — Détection IA
  ai_detector.py              → K-Means clustering (scikit-learn, sans GPU, recommandé)
  deep_learning_detector.py   → TinyCD (PyTorch, poids levir_best.pth)

Étape 4 — Extraction des régions
  ndbi_calculator.py
    extract_change_regions(mask, min_size=2)
    → composantes connexes (scipy.ndimage.label)
    → chaque région = {centroid, bbox, size_pixels}

Étape 5 — Vérification 4 couches
  verification_4_couches.py
    DetectionPipeline.verify_detection(region)
    Couche 1 : Google Buildings V3 (confidence ≥ 0.75 → faux positif)
    Couche 2 : Plan cadastral (forbidden→rouge, conditional→orange, buildable→vert)
    Couche 3 : Cohérence NDBI T1/T2/BSI (filtre démolitions faussement détectées)
    Couche 4 : Surface ≥ 200m², coordonnées dans BBOX Treichville
```

### Management commands

Chaque import/export/pipeline = une commande Django dans `management/commands/` :

```
import_cadastre.py         → lit data_use/cadastre_*.geojson → crée ZoneCadastrale
import_sentinel.py         → lit data_use/sentinel_api_exports/ → crée ImageSatellite
import_sentinel_api.py     → télécharge via API → crée TIF + ImageSatellite
import_google_buildings.py → GEE FeatureCollection → bulk_create MicrosoftFootprint
import_google_temporal_v1.py → GEE ImageCollection de tuiles S2 (pas importable en masse)
export_footprints.py       → MicrosoftFootprint → GeoJSON (backup)
run_detection.py           → pipeline principal complet
pipeline_check.py          → volet 1 vérification + volet 2 détection
```

### API REST

Routes dans `module1_urbanisme/urls.py`, branchées dans `config/urls.py` sous `/api/v1/` :

```python
# ViewSets DRF dans views.py
ZoneCadastraleViewSet         → /api/v1/zones-cadastrales/
DetectionConstructionViewSet  → /api/v1/detections/
ImageSatelliteViewSet         → /api/v1/images/

# Vues fonctionnelles dans views.py
dashboard_resume              → /api/v1/dashboard/resume/
detection_statistics          → /api/v1/detections/statistics/

# Vues web HTML dans views_web.py
dashboard                     → /
detections_list               → /detections/
detection_detail              → /detections/{id}/
zones_list                    → /zones/
```

---

## 3. Guide — Créer le Module 2 (Agroécologie)

Le squelette `module2_agroecologie/` existe déjà. Voici comment le développer complètement.

### Étape 1 — Définir les modèles

```python
# module2_agroecologie/models.py

from django.contrib.gis.db import models

class ZoneAgricole(models.Model):
    """Zone agricole surveillée (équivalent de ZoneCadastrale en M1)"""
    nom = models.CharField(max_length=200)
    culture_principale = models.CharField(max_length=100, blank=True)
    geometry = models.PolygonField(srid=4326, null=True)
    # Ajouter les champs spécifiques agroécologie...

    class Meta:
        verbose_name = "Zone Agricole"

class ImageSatelliteAgro(models.Model):
    """Images satellites pour analyse végétation (réutilise la même structure que M1)"""
    date_acquisition = models.DateField()
    bands = models.JSONField(default=dict)  # B04/B08/B11/SCL comme M1
    zone = models.ForeignKey(ZoneAgricole, on_delete=models.CASCADE, null=True)

class AlerteDeforestation(models.Model):
    """Alerte de déforestation ou de changement de culture (équivalent DetectionConstruction)"""
    STATUT_CHOICES = [
        ('deforestation', 'Déforestation confirmée'),
        ('changement_culture', 'Changement de culture'),
        ('surveillance', 'En surveillance'),
    ]
    date_detection = models.DateTimeField(auto_now_add=True)
    zone = models.ForeignKey(ZoneAgricole, on_delete=models.CASCADE, null=True)
    geometry = models.PolygonField(srid=4326, null=True)
    ndvi_t1 = models.FloatField()   # NDVI avant
    ndvi_t2 = models.FloatField()   # NDVI après
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES)
    confidence = models.FloatField(default=0.0)
```

### Étape 2 — Enregistrer dans INSTALLED_APPS

```python
# config/settings.py — déjà enregistré normalement, vérifier :
INSTALLED_APPS = [
    ...
    'module1_urbanisme',
    'module2_agroecologie',   # ← vérifier que c'est présent
    'module3_orpaillage',
]
```

### Étape 3 — Créer et appliquer les migrations

```bash
python manage.py makemigrations module2_agroecologie
python manage.py migrate
```

### Étape 4 — Créer le pipeline NDVI

```python
# module2_agroecologie/pipeline/ndvi_calculator.py
# S'inspirer de module1_urbanisme/pipeline/ndbi_calculator.py

import numpy as np
import rasterio

def calculate_ndvi(b04_path: str, b08_path: str) -> np.ndarray:
    """NDVI = (B08 - B04) / (B08 + B04) — Végétation, valeurs -1 à +1"""
    with rasterio.open(b04_path) as r4, rasterio.open(b08_path) as r8:
        b04 = r4.read(1).astype(float)
        b08 = r8.read(1).astype(float)
    denom = b08 + b04
    ndvi = np.where(denom == 0, 0.0, (b08 - b04) / denom)
    return np.clip(ndvi, -1.0, 1.0)

def calculate_ndwi(b03_path: str, b08_path: str) -> np.ndarray:
    """NDWI = (B03 - B08) / (B03 + B08) — Eau, valeurs -1 à +1"""
    # Utile pour détecter les surfaces irriguées
    ...

def detect_vegetation_loss(ndvi_t1, ndvi_t2, threshold=0.15) -> np.ndarray:
    """Pixels où NDVI a baissé de plus de threshold → perte de végétation"""
    return (ndvi_t1 - ndvi_t2) > threshold
```

### Étape 5 — Créer la management command

```python
# module2_agroecologie/management/commands/run_detection_agro.py
# S'inspirer de module1_urbanisme/management/commands/run_detection.py

from django.core.management.base import BaseCommand
from module2_agroecologie.models import ImageSatelliteAgro, AlerteDeforestation
from module2_agroecologie.pipeline.ndvi_calculator import calculate_ndvi, detect_vegetation_loss

class Command(BaseCommand):
    help = "Pipeline de détection de déforestation"

    def add_arguments(self, parser):
        parser.add_argument("--date-t1", type=str, required=True)
        parser.add_argument("--date-t2", type=str, required=True)

    def handle(self, *args, **options):
        # Récupérer les images
        img_t1 = ImageSatelliteAgro.objects.get(date_acquisition=options["date_t1"])
        img_t2 = ImageSatelliteAgro.objects.get(date_acquisition=options["date_t2"])

        # Calcul NDVI
        ndvi_t1 = calculate_ndvi(img_t1.bands["B04"], img_t1.bands["B08"])
        ndvi_t2 = calculate_ndvi(img_t2.bands["B04"], img_t2.bands["B08"])

        # Détection des pertes
        mask_deforestation = detect_vegetation_loss(ndvi_t1, ndvi_t2)

        # Extraction régions + sauvegarde...
        self.stdout.write(self.style.SUCCESS("Pipeline agroécologie terminé"))
```

### Étape 6 — Brancher les URLs

```python
# module2_agroecologie/urls.py (créer ce fichier)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('alertes', AlerteDeforestationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
```

```python
# config/urls.py — ajouter :
urlpatterns = [
    ...
    path('api/v2/', include('module2_agroecologie.urls')),   # ← ajouter
    path('module2/', include('module2_agroecologie.urls')),  # ← pour l'UI web
]
```

### Étape 7 — Tests

```python
# test_special/test_AGRO.py (créer ce fichier en s'inspirant de test_PIPE.py)
# Ajouter "AGRO" dans la liste SUITES de run_tests.py
```

---

## 4. Guide — Créer le Module 3 (Orpaillage)

Même pattern que Module 2. Indices spectraux recommandés pour l'orpaillage :

```
MNDWI  = (B03 - B11) / (B03 + B11)  → Turbidité de l'eau (terres déblayées)
NDTI   = (B04 - B03) / (B04 + B03)  → Turbidité (rouge - vert)
Band11 élevé + NDVI bas               → Sol nu / boue = indice d'orpaillage
```

### Structure suggérée

```
module3_orpaillage/
├── models.py
│   ├── CoursDEau              # Rivière surveillée avec géométrie
│   ├── ImageSatelliteOrp      # Images satellites pour la zone
│   └── AlerteOrpaillage       # Alerte orpaillage avec coordonnées GPS
├── pipeline/
│   ├── turbidite_calculator.py  # MNDWI, NDTI
│   └── orpaillage_detector.py   # Détection zones d'orpaillage
└── management/commands/
    └── run_detection_orp.py
```

---

## 5. Indices spectraux par module

| Indice | Formule | Module | Usage |
|---|---|---|---|
| **NDBI** | (B11−B08)/(B11+B08) | M1 | Surfaces bâties |
| **BSI** | (B11+B04−B08)/(B11+B04+B08) | M1 | Sol nu (terrassement) |
| **NDVI** | (B08−B04)/(B08+B04) | M1+M2 | Végétation |
| **NDWI** | (B03−B08)/(B03+B08) | M1+M2 | Eau / humidité |
| **BUI** | NDBI − NDVI | M1 | Built-Up Index (filtre végétation) |
| **MNDWI** | (B03−B11)/(B03+B11) | M3 | Turbidité rivières |
| **NDTI** | (B04−B03)/(B04+B03) | M3 | Turbidité (couleur eau) |

---

## 6. Conventions de code

### Nommage

- **Modèles** : `NomEnPascalCase` (ex: `AlerteDeforestation`, `ZoneAgricole`)
- **Commandes** : `run_detection_agro.py`, `import_zones_agro.py`
- **Pipeline** : fichiers nommés selon leur fonction (`ndvi_calculator.py`, `turbidite_calculator.py`)

### Structure d'une commande Django

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description courte de la commande"

    def add_arguments(self, parser):
        parser.add_argument("--date-t1", type=str, help="Date T1 (YYYY-MM-DD)")
        parser.add_argument("--dry-run", action="store_true", help="Sans écriture en base")

    def handle(self, *args, **options):
        self.stdout.write("Début...")
        # Code ici
        self.stdout.write(self.style.SUCCESS("Terminé"))
```

### Modèle avec géométrie PostGIS

```python
from django.contrib.gis.db import models  # Pas django.db.models

class MonModele(models.Model):
    geometry = models.PolygonField(srid=4326, null=True)
    # Toujours srid=4326 (WGS84) pour cohérence avec le reste du projet
```

### Lire un fichier TIF avec rasterio

```python
import rasterio
import numpy as np

with rasterio.open(chemin_tif) as src:
    array = src.read(1).astype(float)   # Bande 1 (unique pour Sentinel-2 mono-bande)
    transform = src.transform            # Transform affine (pixel → coordonnées géo)
    crs = src.crs                        # Système de référence
```

---

## 7. Workflow Git

### Règles absolues

- ❌ **Jamais** `git push -f` sur `main`
- ❌ **Jamais** commiter `.env`, `db.sqlite3`, `venv/`, `*.pth` > 50 Mo
- ❌ **Jamais** `pip freeze > requirements.txt` (écrase les commentaires du fichier)
- ❌ **Jamais** modifier les migrations d'un autre module sans accord

### Branches

```
feature/module2-nom-fonctionnalite
feature/module3-nom-fonctionnalite
bugfix/module1-description-bug
hotfix/description-urgente
```

### Cycle quotidien

```bash
# Matin — récupérer les derniers changements
git checkout main
git pull origin main

# Créer sa branche de travail
git checkout -b feature/module2-detection-ndvi

# Travailler, commiter souvent
git add module2_agroecologie/models.py
git commit -m "feat(mod2): ajout modèle AlerteDeforestation avec géométrie PostGIS"

# Pousser sa branche
git push -u origin feature/module2-detection-ndvi

# Créer une Pull Request sur GitHub avant de fusionner sur main
```

### Format des messages de commit

```
feat(mod2):     nouvelle fonctionnalité Module 2
fix(mod1):      correction bug Module 1
docs:           documentation uniquement
test(mod2):     ajout ou correction de tests
refactor(mod2): refactorisation sans changement de comportement
chore:          tâche de maintenance (dépendances, config)
```

### Résoudre un conflit

```bash
git checkout ma-branche
git pull origin main          # Récupère les nouveautés de main
# Résoudre les blocs <<< === >>> dans VSCode
git add fichier_corrige.py
git commit -m "fix: résolution conflit avec main"
git push
```

---

## 8. Vérification avant tout push

```bash
# Obligatoire — 0 erreur tolérée
python manage.py check

# Suites de tests (doit rester 0 FAIL)
python run_tests.py --fast

# Vérification système complète
python manage.py pipeline_check --verify-only
```

---

## 9. Ajouter un test pour son module

```python
# test_special/test_AGRO.py
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

RESULTS = []

def ok(name):
    RESULTS.append(("OK", name))
    print(f"  [OK]   {name}")

def fail(name, detail=""):
    RESULTS.append(("FAIL", name, detail))
    print(f"  [FAIL] {name}")
    if detail:
        print(f"         {detail[:300]}")

print("\n=== TEST AGRO : Module 2 Agroécologie ===\n")

import django
django.setup()

# AGRO-01 : Modèles importables
try:
    from module2_agroecologie.models import ZoneAgricole, AlerteDeforestation
    ok("AGRO-01 : Modèles Module 2 importables")
except Exception as e:
    fail("AGRO-01 : Modèles Module 2", str(e)[:200])

# AGRO-02 : NDVI calculator
try:
    from module2_agroecologie.pipeline.ndvi_calculator import calculate_ndvi
    ok("AGRO-02 : calculate_ndvi importable")
except Exception as e:
    fail("AGRO-02 : ndvi_calculator", str(e)[:200])

# Ajouter d'autres tests...

print("\n--- RÉSUMÉ AGRO ---")
nb_ok   = sum(1 for r in RESULTS if r[0] == "OK")
nb_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"OK: {nb_ok} | FAIL: {nb_fail} | TOTAL: {nb_ok+nb_fail}")
```

Puis ajouter `"AGRO"` dans `run_tests.py` :

```python
ALL_SUITES = ["ENV", "DB", "DB_REAL", "PIPE", "PIPE_REAL", "API", "WEB", "CMD", "ROB", "CIV", "AGRO"]
```

---

## 10. Réutiliser le pipeline Sentinel-2 de Module 1

Tous les modules peuvent réutiliser les composants de Module 1 sans les copier.

```python
# Dans module2_agroecologie/ — importer directement depuis M1
from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher
from module1_urbanisme.models import ImageSatellite   # Réutiliser les mêmes images

# NDBICalculator contient aussi calculate_ndvi, calculate_bsi, extract_change_regions, etc.
calc = NDBICalculator()
ndvi = calc.calculate_ndvi(b04_path, b08_path)
regions = calc.extract_change_regions(mask, min_size=2)
```

Les images Sentinel-2 en base (`ImageSatellite`) sont partagées — tous les modules peuvent les utiliser. Il n'est pas nécessaire de ré-importer des images si elles couvrent la même zone et les mêmes dates.

---

## 11. Documentation des fichiers clés

| Fichier | À lire pour... |
|---|---|
| `README.md` | Vue d'ensemble, installation, toutes les commandes |
| `analyse_complet_1.F.md` | Audit technique exhaustif Module 1 (142 Ko) — todos les bugs connus, corrections, limitations |
| `AUDIT FINAL MODULE 1.md` | Résumé non-technique du pipeline pour la présentation |
| `module1_urbanisme/pipeline/verification_4_couches.py` | Comprendre la logique de classification rouge/orange/vert/veille |
| `module1_urbanisme/management/commands/run_detection.py` | Comprendre le pipeline complet (800 lignes, très documenté) |
