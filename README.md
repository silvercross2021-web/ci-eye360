# CIV-EYE COMMAND CENTER 🛰️
### Surveillance Satellitaire Urbaine — Projet SIADE Hackathon · Côte d'Ivoire

**CIV-EYE** est un système Django de surveillance urbaine par satellite. Il détecte automatiquement les constructions illégales en croisant des images Sentinel-2 avec les données cadastrales d'Abidjan (Treichville). Le pipeline compare deux dates satellite (T1 et T2), calcule des indices spectraux (NDBI, BSI, NDVI), applique une IA K-Means ou un réseau de neurones (TinyCD), valide les candidats via 4 couches de vérification croisée, et génère des alertes géolocalisées consultables sur carte interactive.

**Repo GitHub :** `https://github.com/silvercross2021-web/ci-eye360`

---

## Résumé de ce qui a été fait (Module 1)

Le **Module 1 — Urbanisme** est entièrement fonctionnel. Voici l'état exact de la base de données en production :

| Donnée | Valeur |
|---|---|
| Bâtiments Google Open Buildings V3 (réels, GEE) | **39 810** empreintes — zone Treichville/Abidjan |
| Zones cadastrales importées | **19** zones du plan V10 de Treichville |
| Images Sentinel-2 en base | **2** dates — T1 = `2024-02-15`, T2 = `2025-01-15` |
| Détections générées (K-Means + TinyCD) | **729** détections géolocalisées |
| Alertes rouges (infraction avérée) | 38 |
| Alertes oranges (zone conditionnelle) | 76 |
| Alertes bleues (surveillance préventive) | 590 |
| Alertes vertes (conforme) | 25 |

---

## État des modules

| Module | Description | Statut |
|---|---|---|
| **Module 1 — Urbanisme** | Détection de constructions illégales (Treichville/Abidjan) | ✅ Complet et fonctionnel |
| Module 2 — Agroécologie | Surveillance des cultures et déforestation | 🔲 Squelette Django vide (modèles à créer) |
| Module 3 — Orpaillage | Détection d'orpaillage illégal dans les rivières | 🔲 Squelette Django vide (modèles à créer) |

---

## Prérequis

- **Python 3.10+**
- **PostgreSQL 16 + PostGIS 3.4** (obligatoire pour les opérations spatiales)
- **GDAL / GEOS** installés au niveau système (fournis par PostGIS sur Windows)
- **Git**

Les APIs satellites sont toutes optionnelles — le pipeline fonctionne en local avec les fichiers TIF déjà présents dans `data_use/sentinel_api_exports/`.

---

## Installation

### Windows (recommandé)

```powershell
git clone https://github.com/silvercross2021-web/ci-eye360.git
cd ci-eye360

# Créer le venv en héritant des librairies système (GDAL, GEOS, NumPy)
.\install_venv.ps1

# Activer le venv
.\venv\Scripts\activate
```

### Linux / Mac

```bash
git clone https://github.com/silvercross2021-web/ci-eye360.git
cd ci-eye360
python -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
# Puis éditer .env avec vos valeurs
```

### Variables obligatoires

| Variable | Description | Exemple |
|---|---|---|
| `SECRET_KEY` | Clé Django — générer : `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` | `django-insecure-...` |
| `DATABASE_URL` | URL PostGIS | `postgis://user:pwd@localhost:5432/siade_db` |
| `POSTGRES_BIN_PATH` | Windows uniquement — chemin vers les DLLs GDAL/GEOS | `C:\Program Files\PostgreSQL\16\bin` |

### Variables optionnelles (sources de données satellite)

| Variable | Description |
|---|---|
| `GEE_PROJECT_ID` | ID projet Google Cloud pour Google Earth Engine (import Buildings V3) |
| `CDSE_TOKEN` | Token Copernicus Data Space (téléchargement Sentinel-2) |
| `SENTINEL_HUB_CLIENT_ID` / `SECRET` | Alternative à CDSE (30 000 unités/mois gratuites) |
| `HUGGINGFACE_TOKEN` | Validation IA cloud HuggingFace (optionnel, améliore la précision) |

Toutes les variables avec leurs valeurs par défaut sont documentées dans `.env.example`.

---

## Premier lancement depuis zéro

```bash
# 1. Migrations de la base de données
python manage.py migrate

# 2. Importer les zones cadastrales de Treichville
python manage.py import_cadastre

# 3. Importer les images Sentinel-2 depuis les fichiers TIF locaux
python manage.py import_sentinel

# 4. Importer les bâtiments de référence Google V3 (nécessite GEE_PROJECT_ID)
python manage.py import_google_buildings

# 5. Lancer le serveur
python manage.py runserver
```

Interface disponible sur `http://127.0.0.1:8000`

---

## Toutes les commandes Django (`manage.py`)

### Import des données

```bash
# Importer les images Sentinel-2 depuis les fichiers TIF locaux
# Lit les sous-dossiers de data_use/sentinel_api_exports/{date}/
python manage.py import_sentinel
python manage.py import_sentinel --folder /chemin/personnalisé
python manage.py import_sentinel --dry-run   # Aperçu sans écriture

# Télécharger les images Sentinel-2 depuis l'API CDSE (nécessite CDSE_TOKEN)
python manage.py import_sentinel_api --date 2024-02-15
python manage.py import_sentinel_api --date 2025-01-15 --source cdse

# Importer les zones cadastrales du plan V10 de Treichville
python manage.py import_cadastre
python manage.py import_cadastre --file chemin/vers/zones.geojson
python manage.py import_cadastre --dry-run

# Importer Google Open Buildings V3 via GEE (39 810 bâtiments en base)
# Prérequis : GEE_PROJECT_ID dans .env + ee.Authenticate() fait une fois
python manage.py import_google_buildings
python manage.py import_google_buildings --min-confidence 0.75   # Plus strict
python manage.py import_google_buildings --dry-run                # Stats seulement

# Analyser les snapshots Temporal V1 Google (ImageCollection GEE, pas importable en masse)
python manage.py import_google_temporal_v1 --list-tiles
python manage.py import_google_temporal_v1 --check-date 2024-02-15

# Exporter les empreintes en GeoJSON (sauvegarde)
python manage.py export_footprints
python manage.py export_footprints --output backup.geojson
python manage.py export_footprints --source Google_V3_2023
```

### Pipeline de détection

```bash
# Vérification système (volet 1) + détection K-Means (volet 2)
# Commande principale recommandée — tout-en-un
python manage.py pipeline_check
python manage.py pipeline_check --verify-only       # Vérification seulement (pas de détection)
python manage.py pipeline_check --mode tinycd       # Deep Learning
python manage.py pipeline_check --mode both         # K-Means + TinyCD
python manage.py pipeline_check --clear-detections  # Repart de zéro
python manage.py pipeline_check --date-t1 2024-02-15 --date-t2 2025-01-15
python manage.py pipeline_check --output rapport.json

# Pipeline de détection bas niveau (contrôle avancé)
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --use-ai
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --use-tinycd
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --use-ai --use-sar
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --download-b03
python manage.py run_detection --clear-previous  # Supprime les détections précédentes
python manage.py run_detection --dry-run         # Simule sans écriture en base
python manage.py run_detection --n-clusters 6   # Ajuster le nombre de clusters K-Means
```

### Authentification Google Earth Engine

```bash
# À faire une seule fois — ouvre le navigateur pour autoriser GEE
python -c "import ee; ee.Authenticate()"

# Vérifier que GEE fonctionne
python -c "import ee, os; from dotenv import load_dotenv; load_dotenv(); ee.Initialize(project=os.getenv('GEE_PROJECT_ID')); print('GEE OK')"
```

---

## Scripts de lancement rapide

Ces deux scripts sont à la racine du projet. Ils sont les points d'entrée principaux.

### `run_tests.py` — Lancer tous les tests

```bash
# Toutes les suites de tests
python run_tests.py

# Suites rapides (sans les tests sur données réelles)
python run_tests.py --fast

# Suites spécifiques
python run_tests.py ENV DB PIPE CMD
python run_tests.py CIV ROB API WEB
```

**Suites disponibles :**

| Suite | Description |
|---|---|
| `ENV` | Variables d'environnement, imports Python, GDAL/GEOS |
| `DB` | Modèles Django, ORM, serializers, migrations |
| `DB_REAL` | Intégrité des données réelles en base (images, zones, footprints) |
| `PIPE` | Pipeline numérique (NDBI, BSI, K-Means) — sans BDD |
| `PIPE_REAL` | Pipeline sur vraies images Sentinel-2 |
| `API` | Endpoints REST DRF |
| `WEB` | Vues Django (dashboard, détections, zones) |
| `CMD` | Management commands (import, export, pipeline_check) |
| `ROB` | Robustesse et cas limites (NaN, zéros, dimensions) |
| `CIV` | Spécificités ivoiriennes (BBOX Treichville, seuils spectraux) |

**Résultat attendu :** `106 OK / 4 WARN (config dev) / 0 FAIL`

### `run_pipeline.py` — Exécuter le pipeline et voir les détections

```bash
# Pipeline complet K-Means (mode par défaut) + affichage détections
python run_pipeline.py

# Afficher seulement les détections déjà en base (sans relancer la détection)
python run_pipeline.py --show-only

# Filtrer par niveau d'alerte
python run_pipeline.py --show-only --filter rouge
python run_pipeline.py --show-only --filter orange
python run_pipeline.py --show-only --filter veille

# Effacer les détections existantes et relancer
python run_pipeline.py --clear

# Pipeline avec les deux moteurs (K-Means + TinyCD)
python run_pipeline.py --mode both --clear

# Exporter toutes les détections en GeoJSON
python run_pipeline.py --show-only --export detections.json

# Avec des dates personnalisées
python run_pipeline.py --date-t1 2024-02-15 --date-t2 2025-01-15
```

---

## Architecture détaillée du Module 1

### Flux du pipeline de détection

```
Images Sentinel-2 TIF (B04/B08/B11/SCL)
         │
         ▼
[1] Calcul d'indices spectraux (ndbi_calculator.py)
    • NDBI T1 = (B11−B08) / (B11+B08)  ← avant construction
    • NDBI T2 = (B11−B08) / (B11+B08)  ← après construction
    • BSI  T2 = (B11+B04−B08) / (B11+B04+B08)  ← détection terrassement
    • NDVI T2 = (B08−B04) / (B08+B04)  ← masque végétation
    • Masque SCL : eau + nuages exclus automatiquement
         │
         ▼
[2] Détection des changements (K-Means ou TinyCD)
    K-Means : segmentation spectrale → masque T1/T2 → diff = nouvelles constructions
    TinyCD  : réseau de neurones deep learning sur paires d'images
         │
         ▼
[3] Extraction des régions (extract_change_regions)
    • Composantes connexes (scipy.label)
    • Filtre taille minimale ≥ 2 pixels (≈200m²)
    • Conversion pixel → coordonnées WGS84 (rasterio transform)
         │
         ▼
[4] Vérification 4 couches (verification_4_couches.py)
    Couche 1 : Google Open Buildings V3 (39 810 bâtiments réels)
               Bâtiment connu confidence ≥ 0.75 → faux positif rejeté
    Couche 2 : Plan cadastral V10 Treichville (19 zones)
               Zone forbidden → ROUGE, conditional → ORANGE, buildable → VERT
    Couche 3 : Cohérence spectrale (NDBI T1 vs T2, BSI, seuils)
               Filtre les incohérences de démolition vs construction
    Couche 4 : Surface minimale (≥200m²), coordonnées dans BBOX
         │
         ▼
[5] Classification et sauvegarde (DetectionConstruction)
    • status: infraction_zonage / sous_condition / conforme / surveillance_preventive
    • alert_level: rouge / orange / vert / veille
    • Géométrie PostGIS, confiance, surface, coordonnées GPS
```

### Structure des fichiers

```
ci-eye360/
│
├── manage.py                          # Point d'entrée Django
├── run_tests.py                       # Lanceur de tous les tests
├── run_pipeline.py                    # Lanceur pipeline + affichage détections
│
├── config/
│   ├── settings.py                    # Configuration Django (GDAL, PostGIS, DRF)
│   ├── urls.py                        # Routes globales (Module 1 + futurs modules)
│   └── wsgi.py
│
├── module1_urbanisme/
│   ├── models.py                      # Modèles PostGIS
│   │   ├── ZoneCadastrale            — 19 zones du plan V10 Treichville
│   │   ├── ImageSatellite            — 2 images Sentinel-2 (T1/T2) avec chemins TIF
│   │   ├── MicrosoftFootprint        — 39 810 empreintes Google V3 (nom historique)
│   │   └── DetectionConstruction     — 729 détections géolocalisées avec statut
│   │
│   ├── pipeline/
│   │   ├── ndbi_calculator.py         # NDBI, BSI (B11+B04-B08), NDVI, NDWI, BUI
│   │   ├── ai_detector.py             # K-Means (scikit-learn), sans GPU
│   │   ├── deep_learning_detector.py  # TinyCD (PyTorch) — poids à télécharger
│   │   ├── verification_4_couches.py  # Vérification croisée anti-faux-positifs
│   │   ├── sentinel_data_fetcher.py   # Acquisition multi-source (CDSE→SH→PC→GEE)
│   │   ├── api_health_checker.py      # Diagnostic de toutes les APIs au démarrage
│   │   ├── b03_downloader.py          # Téléchargement B03 CDSE + calcul NDWI
│   │   ├── b03_synthesizer.py         # Synthèse B03 = 0.75×B04 + 0.25×B08
│   │   ├── gee_composite.py           # Composites multi-temporels GEE
│   │   ├── huggingface_ai_client.py   # Validation IA cloud HuggingFace
│   │   ├── sentinel1_sar.py           # Radar Sentinel-1 (structuré, non fonctionnel)
│   │   └── tinycd_models/             # Architecture TinyCD PyTorch
│   │
│   ├── management/commands/
│   │   ├── run_detection.py           # Pipeline principal (NDBI + K-Means/TinyCD)
│   │   ├── pipeline_check.py          # 2 volets : vérification + détection
│   │   ├── import_sentinel.py         # Import TIF locaux → ImageSatellite
│   │   ├── import_sentinel_api.py     # Téléchargement API → TIF + ImageSatellite
│   │   ├── import_google_buildings.py # Google Open Buildings V3 via GEE
│   │   ├── import_google_temporal_v1.py # Snapshots V1 GEE (ImageCollection)
│   │   ├── import_cadastre.py         # Zones cadastrales depuis GeoJSON
│   │   └── export_footprints.py       # Export footprints → GeoJSON backup
│   │
│   ├── data_use/
│   │   ├── sentinel_api_exports/
│   │   │   ├── 2024-02-15/            # T1 : B04, B08, B11, SCL (TIF)
│   │   │   └── 2025-01-15/            # T2 : B04, B08, B11, SCL (TIF)
│   │   ├── weights/
│   │   │   └── model_weights.pth      # Poids TinyCD (1.2 Mo, inclus)
│   │   └── backup_footprints_microsoft.geojson  # Backup des 39 810 empreintes
│   │
│   ├── views.py                       # API REST DRF (ViewSets)
│   ├── views_web.py                   # Vues HTML Django (dashboard, carte)
│   ├── serializers.py                 # Sérialisation JSON pour l'API
│   ├── serializers_simple.py          # Serializers légers pour /api/v2/
│   ├── urls.py                        # Routes Module 1
│   ├── admin.py                       # Interface admin Django
│   └── migrations/                    # Migrations PostGIS
│
├── module2_agroecologie/              # Squelette vide — à développer
├── module3_orpaillage/                # Squelette vide — à développer
│
├── templates/
│   └── module1/
│       ├── base.html                  # Layout "Cyber Tactique" dark mode
│       ├── dashboard.html             # Carte interactive + statistiques
│       ├── detections_list.html       # Liste paginée des détections
│       └── detection_detail.html      # Détail d'une détection avec carte
│
├── tests/
│   ├── test_corrections_d1_d18.py     # Tests de validation des corrections D1-D18
│   └── test_pipeline_validation.py    # Validation pipeline sur données réelles
│
├── test_special/                      # Suites de tests détaillées
│   ├── test_ENV.py                    # Environnement + dépendances
│   ├── test_DB.py                     # Modèles + ORM
│   ├── test_DB_REAL.py                # Données réelles en base
│   ├── test_PIPE.py                   # Pipeline numérique
│   ├── test_PIPE_REAL.py              # Pipeline sur vraies images
│   ├── test_API.py                    # Endpoints REST
│   ├── test_WEB.py                    # Vues Django
│   ├── test_CMD.py                    # Management commands
│   ├── test_ROB.py                    # Robustesse et cas limites
│   └── test_CIV.py                    # Contexte ivoirien Treichville
│
├── .env.example                       # Toutes les variables configurables
├── install_venv.ps1                   # Script installation Windows
└── requirements.txt                   # Dépendances Python
```

---

## API REST (Module 1)

L'API est accessible via DRF Browsable API sur `http://127.0.0.1:8000/api/v1/`

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/v1/zones-cadastrales/` | GET | Liste des 19 zones cadastrales |
| `/api/v1/detections/` | GET | Liste paginée des détections (filtres disponibles) |
| `/api/v1/detections/{id}/` | GET / PATCH | Détail + mise à jour statut terrain |
| `/api/v1/detections/statistics/` | GET | Statistiques globales |
| `/api/v1/dashboard/resume/` | GET | Résumé pour le dashboard |
| `/api/statistics/` | GET | Stats format web |
| `/api/detections-geojson/` | GET | Toutes les détections en GeoJSON |
| `/api/zones-geojson/` | GET | Toutes les zones en GeoJSON |

**Filtres disponibles sur `/api/v1/detections/` :**

```
?alert_level=rouge          → alertes rouges uniquement
?status=infraction_zonage   → par statut
?ordering=-confidence       → tri par confiance décroissante
?ordering=date_detection    → tri par date
```

---

## Niveaux d'alerte

| Niveau | Couleur | Statut | Signification |
|---|---|---|---|
| `rouge` | 🔴 | `infraction_zonage` | Construction dans une zone **interdite** — infraction avérée |
| `orange` | 🟠 | `sous_condition` | Construction dans une zone **conditionnelle** — inspection requise |
| `veille` | 🔵 | `surveillance_preventive` | Terrassement / changement détecté — pas encore un bâtiment formé |
| `vert` | 🟢 | `conforme` | Construction dans une zone **constructible** — conforme au plan |

---

## Sources de données

| Source | Clé requise | Usage dans le projet |
|---|---|---|
| **Fichiers TIF locaux** | Non | Source principale — déjà présents dans `data_use/sentinel_api_exports/` |
| **Copernicus CDSE** | Compte gratuit | Téléchargement de nouvelles images Sentinel-2 |
| Sentinel Hub | Optionnelle | Fallback si CDSE indisponible |
| **Google Earth Engine** | Oui (`GEE_PROJECT_ID`) | Google Open Buildings V3 (39 810 bâtiments) |
| Google Open Buildings Temporal V1 | Oui (GEE) | Snapshots annuels 2016-2023 (structure ImageCollection) |
| HuggingFace API | Optionnelle | Validation IA cloud des détections |
| Sentinel-1 SAR | Non fonctionnel | Structuré dans le code, non opérationnel |

---

## TinyCD — Deep Learning

Le modèle TinyCD est déjà présent dans `module1_urbanisme/data_use/weights/model_weights.pth` (1.2 Mo).

Si le fichier est absent ou corrompu :
1. Télécharger `levir_best.pth` depuis : `https://github.com/AndreaCodegoni/Tiny_model_4_CD/tree/main/pretrained_models`
2. Renommer en `model_weights.pth`
3. Placer dans `module1_urbanisme/data_use/weights/`

> **Note :** Les poids TinyCD ont été entraînés sur des images 0.5m (USA/Chine). Sur Sentinel-2 à 10m, les résultats sont moins précis qu'avec K-Means. Utiliser `--use-ai` (K-Means) pour la production.

---

## Comment continuer — Modules 2 et 3

Les dossiers `module2_agroecologie/` et `module3_orpaillage/` sont des squelettes Django vides. Voir **CONTRIBUTING.md** pour le guide complet de création d'un nouveau module.

Résumé rapide :

```bash
# Créer les modèles du module 2
# Éditer module2_agroecologie/models.py

# Créer les migrations
python manage.py makemigrations module2_agroecologie
python manage.py migrate

# Brancher dans config/urls.py
# Ajouter le module dans config/settings.py INSTALLED_APPS
```

---

## Documentation technique

| Fichier | Contenu |
|---|---|
| `CONTRIBUTING.md` | Architecture détaillée, guide création Module 2/3, workflow Git |
| `analyse_complet_1.F.md` | Audit technique exhaustif Module 1 (142 Ko) — tous les bugs et corrections |
| `AUDIT FINAL MODULE 1.md` | Résumé non-technique du pipeline |
| `pipeline_report_*.json` | Dernier rapport de vérification système généré par `pipeline_check` |

---

> **Design :** L'interface utilise le thème "Cyber Tactique" (dark mode). Ne pas écraser les variables CSS `:root` dans `templates/module1/base.html`.