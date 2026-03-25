# CIV-EYE COMMAND CENTER 🛰️
### Surveillance Satellitaire — Projet SIADE Hackathon · Côte d'Ivoire

**CIV-EYE** détecte automatiquement les constructions illégales en croisant des images satellites Sentinel-2 avec les données cadastrales d'Abidjan. Le système compare deux dates, calcule des indices spectraux (NDBI, BSI), applique de l'IA, et génère des alertes géolocalisées consultables sur carte.

---

## État du projet

| Module | Description | Statut |
|---|---|---|
| **Module 1 — Urbanisme** | Détection de constructions illégales (Treichville/Abidjan) | ✅ Fonctionnel |
| Module 2 — Agroécologie | Surveillance des cultures et déforestation | 🔲 Squelette vide |
| Module 3 — Orpaillage | Détection d'orpaillage illégal dans les rivières | 🔲 Squelette vide |

---

## Prérequis

- **Python 3.10+** avec GDAL/GEOS installés système (PostGIS)
- **PostgreSQL 16 + PostGIS** (développement local possible en SQLite sans SIG avancé)
- **Git**

Les APIs satellites sont toutes optionnelles — le pipeline fonctionne sans clé via **Copernicus CDSE (gratuit)**.

---

## Installation

### Option A — Windows (recommandé)

Un script automatique crée le venv avec l'héritage système (GDAL, GEOS, NumPy) :

```powershell
git clone https://github.com/votre-org/ci-eye360.git
cd ci-eye360
.\install_venv.ps1
.\venv\Scripts\activate
```

### Option B — Linux / Mac

```bash
git clone https://github.com/votre-org/ci-eye360.git
cd ci-eye360
python -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
```

Ouvrez `.env` et renseignez au minimum :

| Variable | Obligatoire | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Générer : `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DATABASE_URL` | ✅ | Format : `postgis://user:password@localhost:5432/siade_db` |
| `POSTGRES_BIN_PATH` | Windows uniquement | Chemin vers `C:\Program Files\PostgreSQL\16\bin` (GDAL/GEOS DLLs) |
| `CDSE_TOKEN` | Optionnel | Token Copernicus pour télécharger les rasters |
| `SENTINEL_HUB_CLIENT_ID/SECRET` | Optionnel | Fallback automatique vers CDSE si absent |
| `GEE_PROJECT_ID` | Optionnel | Google Earth Engine (composites multi-temporels) |

Toutes les variables sont documentées dans `.env.example`.

---

## Premier lancement

```bash
python manage.py migrate
python manage.py runserver
```

→ Interface disponible sur [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Commandes principales

### Lancer une détection

```bash
# Détection K-Means standard (rapide, sans GPU)
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --use-ai

# Détection Deep Learning TinyCD (nécessite model_weights.pth)
python manage.py run_detection --date-t1 2024-02-15 --date-t2 2025-01-15 --use-tinycd
```

> **TinyCD** : télécharger `levir_best.pth` depuis [HuggingFace](https://huggingface.co/nicikess/tinycd) et le placer dans `module1_urbanisme/data_use/weights/model_weights.pth`.

### Importer les données de référence

```bash
# Importer Google Open Buildings V3 (bâtiments connus)
python manage.py import_microsoft

# Importer les zones cadastrales
python manage.py import_cadastre

# Télécharger la bande B03 Sentinel-2 depuis CDSE
python manage.py run_detection --download-b03 --date-t1 2024-02-15
```

### Tests

```bash
# Tests unitaires Django (5 tests du pipeline)
python manage.py test module1_urbanisme

# Validation complète des corrections (11 points)
python tests/test_corrections_d1_d18.py

# Vérification de la configuration Django
python manage.py check
```

---

## Structure du projet

```
ci-eye360/
├── config/                        # Configuration Django (settings, URLs, base)
├── core/                          # Utilitaires globaux
├── module1_urbanisme/             # [MODULE 1] Détection de constructions illégales
│   ├── pipeline/                  # Cœur algorithmique
│   │   ├── sentinel_data_fetcher.py  # Acquisition multi-source (CDSE, SH, PC, GEE)
│   │   ├── ndbi_calculator.py        # Indices spectraux (NDBI, BSI, NDVI, NDWI)
│   │   ├── ai_detector.py            # K-Means clustering
│   │   ├── deep_learning_detector.py # TinyCD (Deep Learning)
│   │   ├── verification_4_couches.py # Validation anti-faux-positifs
│   │   └── b03_downloader.py         # Téléchargement bande B03 CDSE
│   ├── data_use/
│   │   ├── sentinel_api_exports/     # Rasters TIF (B04/B08/B11/SCL par date)
│   │   └── weights/                  # Poids TinyCD (model_weights.pth — à télécharger)
│   ├── management/commands/       # Commandes CLI Django
│   ├── models.py                  # Modèles PostGIS (DetectionConstruction, etc.)
│   ├── views.py                   # API REST (DRF)
│   └── serializers.py             # Sérialisation JSON
├── module2_agroecologie/          # [MODULE 2] Squelette vide
├── module3_orpaillage/            # [MODULE 3] Squelette vide
├── templates/                     # Interface web "Cyber Tactique" (dark mode)
├── static/                        # CSS / JS / icônes
├── tests/                         # Scripts de validation
├── .env.example                   # Modèle de configuration
├── install_venv.ps1               # Script d'installation Windows
└── requirements.txt               # Dépendances Python
```

---

## Documentation

| Fichier | Public cible | Contenu |
|---|---|---|
| [**AUDIT FINAL MODULE 1.md**](./AUDIT%20FINAL%20MODULE%201.md) | Tout public | Explication simplifiée du fonctionnement du pipeline (non-technique) |
| [**analyse_complet_1.F.md**](./analyse_complet_1.F.md) | Développeurs | Audit technique exhaustif : chaque fichier expliqué, tous les bugs, toutes les corrections |
| [**CONTRIBUTING.md**](./CONTRIBUTING.md) | Développeurs | Règles Git, workflow de contribution, normes de code |

---

## Sources de données satellites

| Source | Clé requise | Usage |
|---|---|---|
| **Copernicus CDSE** | Non (compte gratuit) | Source principale — bandes B03/B04/B08/B11/SCL |
| Sentinel Hub | Optionnelle | 30 000 unités/mois gratuites |
| Microsoft Planetary Computer | Non | Fallback STAC |
| Google Earth Engine | Oui (compte GEE) | Open Buildings V3, composites multi-temporels |
| Sentinel-1 SAR | Non (clé entreprise payante) | Structuré dans le code, non fonctionnel actuellement |

---

> **Design :** L'interface utilise le thème "Cyber Tactique" (dark mode). Ne pas écraser les variables `:root` dans `templates/module1/base.html`.