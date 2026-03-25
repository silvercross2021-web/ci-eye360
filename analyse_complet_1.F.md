# 📖 RAPPORT COMPLET D'ANALYSE — CIV-EYE MODULE 1
### Projet SIADE Hackathon — Surveillance du Bâti par Satellite, Treichville, Abidjan

---

> **Date d'analyse :** Mars 2026  
> **Périmètre :** Intégralité du dépôt `SIADE_hackathon` (corpus `silvercross2021-web/ci-eye360`)  
> **Méthode :** Lecture exhaustive de chaque fichier source, identification des flux, audit des bugs

---

## 🧭 SECTION 1 — CONTEXTE ET OBJECTIF DU PROJET

---

### 1.1 — Quel est le problème que ce projet cherche à résoudre ?

En Côte d'Ivoire, et plus précisément dans le quartier de **Treichville à Abidjan**, de nombreuses constructions sont réalisées sans permis, sur des zones interdites (zones inondables, zones portuaires, servitudes) ou sans respecter les conditions imposées par le plan de zonage officiel. Ces infractions sont difficiles à détecter manuellement : la ville est dense, les ressources des agents cadastraux sont limitées, et le contrôle terrain ne peut pas couvrir l'ensemble du territoire en temps réel.

**CIV-EYE** résout ce problème en automatisant la surveillance depuis l'espace. En comparant des images satellites prises à deux dates différentes (T1 = janvier 2024 et T2 = janvier 2025), le système identifie automatiquement les zones où le sol a changé de nature (apparition de béton, de tôle, de terrassement), puis croise ces détections avec le cadastre officiel pour déterminer si la construction est légale ou non. Le résultat est une alerte classée par niveau de gravité, transmissible aux agents de terrain.

---

### 1.2 — Qui utilise ce projet et dans quel contexte ?

**Utilisateur primaire :** Agent municipal ou inspecteur cadastral de la ville d'Abidjan. Il reçoit une liste d'alertes géolocalisées sur un tableau de bord web. Pour chaque alerte, il peut voir les coordonnées exactes, le niveau de confiance du système, et le type d'infraction (zone interdite, zone sous condition). Il peut confirmer l'alerte, la marquer comme faux positif, ou lancer une investigation terrain. Un bouton "Vérifier en HD sur Google Maps" l'emmène directement sur les coordonnées GPS en vue satellite haute résolution.

**Utilisateur secondaire :** Développeur ou analyste qui alimente le pipeline en images satellites, lance les commandes d'import et de détection, et consulte les statistiques.

Le projet manipule des données raster satellitaires multi-spectrales (bandes B04 Rouge, B08 NIR, B11 SWIR de Sentinel-2), des fichiers GeoJSON du cadastre, des empreintes de bâtiments issues de Google Open Buildings V3, et produit des enregistrements géoréférencés stockés en base de données spatiale PostGIS.

---

### 1.3 — Quel est le périmètre fonctionnel du projet ?

**Ce que le projet fait aujourd'hui :**
- Acquisition multi-source d'images Sentinel-2 L2A (Sentinel Hub, Copernicus CDSE gratuit, Microsoft Planetary Computer)
- Calcul d'indices spectraux (NDBI, BSI, NDVI, BUI, NDWI)
- Détection de changements bi-temporels (nouvelles constructions, terrassements, démolitions)
- Vérification en 4 couches (Google Open Buildings, Sentinel T1, Sentinel T2, cadastre)
- Classification des alertes en 4 niveaux (rouge / orange / vert / veille)
- Interface web de visualisation cartographique (Leaflet.js)
- API REST complète pour consommation externe (Django REST Framework)
- Tableau de bord avec statistiques et graphiques

**Ce que le projet ne fait pas encore :**
- Modules 2 (Agroécologie) et 3 (Orpaillage) sont des squelettes vides sans aucune logique métier
- Sentinel-1 SAR (radar anti-nuage) est structuré dans le code mais non fonctionnel (nécessite une clé API entreprise payante)
- Le compositing Google Earth Engine (GEE) nécessite une intervention manuelle (compte à créer, script à déployer)
- La comparaison temporelle Google Buildings V1 (pour distinguer bâtiment pré-existant vs nouvelle construction récente) n'est pas implémentée — risque de faux négatifs
- Pas d'export PDF natif fonctionnel (WeasyPrint en dépendance mais non utilisé)
- Pas de tâches asynchrones Celery (en dépendance mais aucun task défini)

---

### 1.4 — Quel est le contexte technique ?

| Élément | Valeur |
|---|---|
| Langage | Python 3.x |
| Framework web | Django 5.0.3 |
| API REST | Django REST Framework 3.15.1 |
| Base de données dev | SQLite (fichier `db.sqlite3`) |
| Base de données prod | PostgreSQL 16 + PostGIS |
| Calcul géospatial | rasterio 1.3.9, numpy, scipy, shapely, django.contrib.gis |
| IA | K-Means (scikit-learn), TinyCD (PyTorch + torchvision) |
| Interface web | Leaflet.js, Chart.js, CSS dark mode "Cyber Tactique" |
| Environnement développement | Windows/Linux/Mac (portabilité assurée par `sys.platform == 'win32'` dans `settings.py`) |
| Serveur dev | `python manage.py runserver` (port 8000) |
| Serveur prod cible | Gunicorn |

---

## 🗂️ SECTION 2 — ANATOMIE COMPLÈTE DU PROJET : CHAQUE FICHIER EXPLIQUÉ

---

### 📁 RACINE DU PROJET

---

#### `manage.py`

**Rôle :** Point d'entrée en ligne de commande pour Django. Sert à lancer le serveur de développement, appliquer les migrations, et exécuter toutes les commandes personnalisées du projet (`run_detection`, `import_sentinel`, `import_cadastre`, etc.).

**Ce qu'il fait :** La fonction `main()` configure la variable d'environnement `DJANGO_SETTINGS_MODULE` à `"config.settings"` puis délègue l'exécution à `django.core.management.execute_from_command_line(sys.argv)`. C'est un boilerplate Django standard.

**Appelé par :** L'utilisateur en ligne de commande via `python manage.py <commande>`.

**Appelle :** `config.settings` (indirectement, via la variable d'environnement).

**Anomalies :** Aucune.

---

#### `requirements.txt`

**Rôle :** Liste officielle des dépendances Python du projet avec leurs versions exactes. Sert à l'installation via `pip install -r requirements.txt`.

**Contenu structuré (6 catégories) :**
- **Django core :** Django==5.0.3, djangorestframework==3.15.1, django-cors-headers==4.3.1, django-filter==24.3, django-environ==0.11.2, django-browser-reload>=1.12.0, psycopg2-binary>=2.9.9 (✅ version fixée)
- **Géospatial :** rasterio==1.3.9, numpy>=1.26.4, scipy>=1.12.0, scikit-image>=0.22.0, opencv-python-headless>=4.9.0, scikit-learn>=1.3.0, shapely>=2.0.3 *(gdal, geopandas, fiona, pyproj sont commentés)*
- **APIs satellitaires :** sentinelhub==3.11.5, planetary-computer==1.0.0, pystac-client==0.8.5, earthengine-api (sans version)
- **Deep Learning :** torch>=2.0.0, torchvision>=0.15.0
- **Asynchrone :** celery==5.3.6, redis==5.0.3 *(phase future — aucun task actif)*
- **Utilitaires :** requests, Pillow, python-dotenv, gunicorn, weasyprint==61.2 *(phase future — aucune vue PDF active)*

**⚠️ Anomalies :**
1. ✅ **CORRIGÉ (B3)** : `django_browser_reload` était absent de `requirements.txt` → `django-browser-reload>=1.12.0` ajouté.
2. ✅ **CORRIGÉ (B4)** : `shapely` était commenté dans `requirements.txt` → `shapely>=2.0.3` décommenté.
3. ✅ **CORRIGÉ** : `psycopg2-binary>=2.9.9` — version minimale fixée.
4. ✅ **DOCUMENTÉ** : `weasyprint==61.2` annoté `(phase future — aucune vue PDF active)` dans `requirements.txt`.
5. ✅ **DOCUMENTÉ** : `celery==5.3.6` / `redis==5.0.3` annotés `(phase future — aucun task actif)` dans `requirements.txt`.

---

#### `.env.example`

**Rôle :** Modèle de fichier de configuration à dupliquer en `.env` avant le premier lancement. Documente exhaustivement toutes les variables d'environnement requises ou optionnelles.

**Variables documentées :**

| Variable | Obligatoire | Rôle |
|---|---|---|
| `SECRET_KEY` | Oui | Clé secrète Django (sécurité CSRF, sessions) |
| `DEBUG` | Oui | Mode debug (True/False) |
| `ALLOWED_HOSTS` | Oui | Domaines autorisés |
| `DATABASE_URL` | Non* | URL PostGIS (`postgis://user:pass@host:port/db`). Si absent → SQLite |
| `SENTINEL_HUB_CLIENT_ID` | Non | Clé API Sentinel Hub (30 000 unités/mois gratuites) |
| `SENTINEL_HUB_CLIENT_SECRET` | Non | Secret API Sentinel Hub |
| `CDSE_TOKEN` | Non | Token Copernicus Data Space (pour grandes images) |
| `GEE_PROJECT_ID` | Non | Projet Google Earth Engine (requis pour Google Open Buildings via GEE) |
| `GOOGLE_MAPS_API_KEY` | Non | Clé Google Maps (non utilisée dans le code actuel) |
| `MICROSOFT_PC_API_KEY` | Non | Clé Microsoft Planetary Computer |
| `HUGGINGFACE_TOKEN` | Non | Token HuggingFace (mode local fonctionne sans token) |
| `NASA_EARTHDATA_USERNAME` | Non | Futur module SAR Sentinel-1 |
| `NASA_EARTHDATA_PASSWORD` | Non | Futur module SAR Sentinel-1 |
| `CELERY_BROKER_URL` | Non | Redis pour tâches asynchrones (non intégrées) |
| `CELERY_RESULT_BACKEND` | Non | Redis pour résultats asynchrones (non intégrées) |
| `SENTRY_DSN` | Non | Télémétrie Sentry (optionnel) |

✅ **CORRIGÉ (D1)** : `CORS_ALLOWED_ORIGINS` décommenté dans `.env.example` avec valeur d'exemple `https://civ-eye.ci,https://admin.civ-eye.ci`. Adapté à chaque environnement de déploiement.

> Note `.env` (non `.env.example`) : token Sentinel Hub `sh-751***` commenté avec instructions de renouvellement — `NASA_EARTHDATA_USERNAME=brandonne` ajouté. ✅ **FAIT**

---

#### `.gitignore`

**Rôle :** Définit les fichiers et répertoires exclus du dépôt Git pour éviter de partager des données sensibles ou volumineuses.

**Exclusions notables :**
- `.env` → clés secrètes et credentials API
- `db.sqlite3` → base de données locale (données potentiellement sensibles)
- `venv/`, `__pycache__/`, `*.pyc` → environnement virtuel et bytecode
- `media/`, `staticfiles/` → fichiers générés
- `*.tif`, `*.tiff`, `*.geojsonl` → données satellitaires volumineuses (plusieurs centaines de Mo)
- `module1_urbanisme/data_use/weights/*.pth` → poids PyTorch (>50 Mo)
- `module1_urbanisme/data_use/sentinel_api_exports/` → images téléchargées via API
- `logs/*.log` → fichiers de log

---

#### `CONTRIBUTING.md`

**Rôle :** Guide de contribution pour l'équipe de 3 développeurs du hackathon. Établit les règles Git et les normes de développement pour éviter les conflits et maintenir la cohérence.

**Règles clés :**
- **Séparation stricte des modules :** chaque développeur travaille sur son module (M1/M2/M3) sans modifier les fichiers des autres
- **Format de branches :** `feature/mod1-nom-tache` ou `bugfix/mod1-nom-bug`
- **Format de commits :** `feat(mod1): description` ou `fix(mod1): description`
- **PR obligatoire :** pas de merge direct sur `main`, review croisée requise
- **Interdiction formelle :** `git push -f` sur `main` est interdit
- **Normes pipeline :** tests unitaires obligatoires pour les nouvelles méthodes de `ndbi_calculator.py`, poids modèles dans `data_use/weights/`, utiliser `SentinelDataFetcher` pour toute acquisition satellite

---

#### `README.md`

**Rôle :** Documentation d'accueil du projet pour les contributeurs et évaluateurs du hackathon. Présente CIV-EYE, ses fonctionnalités, et les commandes de lancement.

**Contenu :**
- Description du projet et des 5 fonctionnalités clés (détection multi-source, vérification 4 couches, classification légale, interface web, API REST)
- Flux de données du pipeline (5 étapes résumées)
- Commandes principales (import_cadastre, import_sentinel_api, run_detection)
- Structure du répertoire
- Guide d'installation rapide (git clone → venv → pip → .env → migrate → runserver)

✅ **CORRIGÉ (D2)** : README mis à jour — `docs/` marqué comme vide avec renvoi vers `NVideDocx/` pour les audits. Structure du répertoire conforme à la réalité du projet.

---

#### `AUDIT FINAL MODULE 1.md`

**Rôle :** Rapport d'audit technique simplifié, rédigé en langue accessible pour un public non-technicien (décideurs, jury du hackathon). Explique le fonctionnement du Module 1 en termes métiers.

**Contenu (73 lignes) :** Explication vulgarisée des 4 sources de données (Sentinel-2 optique, Sentinel-1 radar, Google/Microsoft empreintes, cadastre V10), du pipeline en 4 étapes (NDBI, vérification 4 couches, IA, masques), tableau des fichiers clés, conclusion d'audit. Conclusion : "Module techniquement robuste, 100% automatisé, multi-source. Points d'attention : nécessite clé API GEE ou CDSE."

---

#### `install_venv.ps1`

**Rôle :** Script PowerShell pour créer l'environnement virtuel Python sur Windows avec héritage des packages système (notamment GDAL et GEOS qui nécessitent des DLLs Windows installées par le package OSGeo4W ou PostgreSQL).

**Ce qu'il fait (4 étapes) :**
1. `python -m venv venv --system-site-packages` → crée le venv en héritant de GDAL/GEOS installés au niveau système, évitant la recompilation C++
2. Mise à jour de pip dans le venv
3. `pip install sentinelhub planetary-computer pystac-client earthengine-api oauthlib requests-oauthlib` → packages satellites
4. `pip install -r requirements.txt` → dépendances complètes du projet (**✅ CORRIGÉ D3**)

✅ **CORRIGÉ (D3)** : Étape 4 ajoutée — `pip install -r requirements.txt` garantit l'installation complète indépendamment de l'environnement système.

---

#### `exports/export_detections_gps.csv`

**Rôle :** Fichier CSV (12 Ko) contenant des détections exportées avec coordonnées GPS (latitude, longitude, niveau d'alerte, statut, NDBI T1/T2, surface, confiance). Généré par `scripts/export_detections_gps.py` pour partage avec les agents terrain ou import dans un SIG.

---

### 📁 config/

---

#### `config/settings.py`

**Rôle :** Configuration centrale de l'application Django. Charge le fichier `.env`, configure tous les paramètres : base de données, logging, CORS, applications installées, templates, fichiers statiques, internationalisation.

**Appelle :** `.env` (via `django-environ`), `rasterio` (pour corriger le conflit PROJ).  
**Est appelé par :** `manage.py`, `wsgi.py`, `asgi.py` via `DJANGO_SETTINGS_MODULE`.

**Contenu structuré :**

*Correction PROJ (lignes 20-35) :*
```python
import rasterio
os.environ['PROJ_LIB'] = rasterio.env.default_proj_lib()
```
Force `PROJ_LIB` vers la base de données PROJ embarquée dans rasterio pour éviter un conflit avec celle de PostgreSQL/PostGIS qui cause des warnings `CPLE_AppDefined PROJ`.

*INSTALLED_APPS (12 applications) :*
- `django.contrib.admin`, `django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`, `django.contrib.messages`, `django.contrib.staticfiles`
- `django.contrib.gis` → support PostGIS, `GISModelAdmin` dans l'admin
- `rest_framework` → Django REST Framework
- `corsheaders` → gestion CORS pour l'API
- `django_filters` → filtrage API
- `django_browser_reload` → rechargement automatique en développement
- `core` → application fondation commune (migrations vides pour l'instant) ✅ **AJOUTÉ (C5)**
- `module1_urbanisme` → l'application principale

*Base de données :*
```python
DATABASES = {'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')}
```
Si `DATABASE_URL=postgis://...` est défini dans `.env` → PostgreSQL/PostGIS. Sinon → SQLite. Sur Windows, les DLL PostgreSQL sont ajoutées au PATH :
```python
POSTGRES_BIN = env('POSTGRES_BIN_PATH', default=r"C:\Program Files\PostgreSQL\16\bin")
```
✅ **CORRIGÉ (C4)** : chemin configurable via variable d'environnement `POSTGRES_BIN_PATH` dans `.env` (fallback Windows par défaut).

*Logging :*
Silences les warnings PROJ de rasterio (niveau ERROR) et les erreurs 403 de GEE (EarthEngine.logger). Écrit dans `logs/civ_eye.txt` en mode append avec rotation (10 Mo max, 5 backups).

*CORS :*
```python
CORS_ALLOW_ALL_ORIGINS = DEBUG
```
Ouvert en développement (`DEBUG=True`), fermé en production.

*Internationalisation :*
```python
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
```

**⚠️ Anomalies :**
1. ✅ **CORRIGÉ (C1)** : `LANGUAGE_CODE` doublon supprimé — seule la valeur `"fr-fr"` subsiste.
2. ✅ **CORRIGÉ (C2)** : `TIME_ZONE` doublon supprimé — seule la valeur `"Africa/Abidjan"` subsiste.
3. ✅ **CORRIGÉ (C4)** : chemin lu depuis `env('POSTGRES_BIN_PATH', default=...)`, configurable via `.env`.
4. ✅ **CORRIGÉ (C3)** : `SECRET_KEY = env('SECRET_KEY')` sans fallback — exception explicite levée si la variable est absente du `.env`.
5. ✅ **CORRIGÉ (B3/C5)** : `django_browser_reload` ajouté dans `requirements.txt` · `"core"` ajouté dans `INSTALLED_APPS`.

---

#### `config/urls.py`

**Rôle :** Routeur URL principal de l'application Django. Distribue les requêtes HTTP entre l'interface HTML, les APIs REST, et l'admin.

**Routes configurées :**
```
admin/                      → interface d'administration Django
""  (préfixe vide)          → module1_urbanisme.urls_web   (pages HTML)
""  (préfixe vide)          → module1_urbanisme.urls       (API REST v1)
"api/v2/"                   → module1_urbanisme.urls_simple (API REST v2) ✅ CORRIGÉ D4
```
En mode `DEBUG` : routes pour les fichiers media, les fichiers statiques, et le live reload Django.

✅ **CORRIGÉ (D4)** : `urls_simple` passé sur préfixe distinct `"api/v2/"` pour éliminer l'ambiguïté des 3 × `include("")`. L'API simplifiée est maintenant accessible sur `GET /api/v2/detections-simple/`.

---

#### `config/wsgi.py`

**Rôle :** Point d'entrée WSGI pour le déploiement en production via Gunicorn, uWSGI, ou Apache avec mod_wsgi. Configure `DJANGO_SETTINGS_MODULE` et expose `application = get_wsgi_application()`. Boilerplate Django standard.

---

#### `config/asgi.py`

**Rôle :** Point d'entrée ASGI pour le déploiement asynchrone via Daphne ou Uvicorn (support WebSockets). Configure `DJANGO_SETTINGS_MODULE` et expose `application = get_asgi_application()`. Boilerplate Django standard. Non utilisé activement (pas de WebSockets dans ce projet).

---

#### `config/__init__.py`

**Rôle :** Marque le répertoire `config/` comme package Python. Fichier vide.

---

### 📁 core/

---

#### `core/models.py`, `core/views.py`, `core/admin.py`, `core/tests.py`

**Rôle prévu :** L'application `core` a été créée comme fondation commune partagée entre les trois modules (Urbanisme, Agroécologie, Orpaillage). Elle devait contenir des modèles de base, des utilitaires partagés, et des classes abstraites.

**État actuel :** Tous ces fichiers sont des stubs vides. `models.py` contient uniquement `from django.db import models` (60 octets). `views.py` est vide (66 octets). `admin.py` et `tests.py` sont des boilerplates Django minimaux.

✅ **CORRIGÉ (C5)** : `"core"` est maintenant dans `INSTALLED_APPS` de `settings.py`. L'application est enregistrée et ses migrations seront correctement appliquées.

---

#### `core/ia/`

**Rôle prévu :** Répertoire destiné aux utilitaires IA partagés entre les modules. Actuellement **vide**.

---

#### `core/migrations/`

**Contenu :** Migration initiale vide (0001_initial.py). Ne crée aucune table.

---

### 📁 module1_urbanisme/

---

#### `module1_urbanisme/apps.py`

**Rôle :** Configuration minimale de l'application Django.

**Contenu :**
```python
class Module1UrbanismeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "module1_urbanisme"
```
`BigAutoField` : les clés primaires auto-incrémentées seront des entiers 64 bits, utile pour les grandes tables comme `MicrosoftFootprint`.

---

#### `module1_urbanisme/models.py`

**Rôle :** Définit les 4 modèles de données du module Urbanisme avec leurs champs, contraintes, index, et méthodes utilitaires. C'est le cœur de la structure de données du projet.

**Appelle :** `django.contrib.gis.db` (champs PostGIS), `django.contrib.auth.models.User`.
**Est appelé par :** Pratiquement tous les autres fichiers du module.

---

**Modèle 1 : `ZoneCadastrale`**

Représente une zone du plan cadastral de Treichville avec ses limites géographiques et son statut légal de constructibilité.

| Champ | Type | Description |
|---|---|---|
| `zone_id` | CharField(50, unique) | Identifiant unique (ex : `TRV_001`) |
| `name` | CharField(200) | Nom descriptif |
| `zone_type` | CharField(50) | Type : `residential`, `commercial`, `industrial`, `mixed`, `green_space`, `water`, `port`, `airport` |
| `buildable_status` | CharField(20) | Statut légal : `buildable`, `conditional`, `forbidden` |
| `geometry` | PolygonField(SRID=4326) | Géométrie polygonale PostGIS en WGS84 |
| `metadata` | JSONField | Données complémentaires : description, bbox, surface_ha |
| `created_at` / `updated_at` | DateTimeField(auto) | Dates d'audit |

Propriété `geometry_geojson` : retourne la géométrie en format GeoJSON string pour sérialisation directe dans les templates et l'API.

```python
BUILDABLE_STATUS_CHOICES = [
    ('buildable', 'Zone Constructible'),
    ('conditional', 'Construction Sous Conditions'),
    ('forbidden', 'Construction Interdite'),
]
```

---

**Modèle 2 : `ImageSatellite`**

Représente une acquisition Sentinel-2 L2A pour une date donnée. Stocke les **chemins absolus** vers les fichiers TIFF des bandes spectrales sur le disque (pas les images elles-mêmes).

| Champ | Type | Description |
|---|---|---|
| `date_acquisition` | DateField | Date de prise de vue |
| `satellite` | CharField(100) | Source (ex : `Sentinel-2_L2A`) |
| `bands` | JSONField | Dict chemins absolus par bande : `{"B04": "/path/B04_2024-01-29.tif", "B08": "...", "B11": "...", "SCL": "..."}` |
| `classification_map` | CharField(500, null) | Chemin vers le fichier SCL |
| `processed` | BooleanField | `True` si déjà traité par `run_detection` |
| `cloud_coverage` | FloatField(null) | Pourcentage de couverture nuageuse |

---

**Modèle 3 : `MicrosoftFootprint`**

Initialement prévu pour les Microsoft Building Footprints (2020), ce modèle contient aujourd'hui les empreintes **Google Open Buildings V3** (mai 2023). Le nom a été conservé pour éviter une migration complexe. Chaque enregistrement est le polygone d'un bâtiment connu, utilisé par la vérification 4 couches pour détecter les pré-existants.

| Champ | Type | Description |
|---|---|---|
| `geometry` | PolygonField(SRID=4326) | Empreinte géométrique du bâtiment |
| `source_file` | CharField(200) | Fichier source (ex : `google_open_buildings_v3`) |
| `source` | CharField(50) | Fournisseur (voir SOURCE_CHOICES) |
| `date_reference` | CharField(20) | Période de référence (ex : `2023-05`) |
| `confidence_score` | FloatField(null) | Score de confiance Google (0.65 → 1.0) |

Index définis sur `source_file`, `source`, et `confidence_score` pour accélérer les requêtes ST_DWithin.

```python
SOURCE_CHOICES = [
    ('Google_V3_2023', 'Google Open Buildings V3 (Mai 2023)'),
    ('Google_Temporal_V1', 'Google Open Buildings Temporal V1'),
    ('Microsoft_2020', 'Microsoft Building Footprints (2020)'),
]
```

---

**Modèle 4 : `DetectionConstruction`**

Modèle central du projet. Représente une détection de changement validée par le pipeline, avec toutes les informations nécessaires pour l'investigation terrain.

| Champ | Type | Description |
|---|---|---|
| `date_detection` | DateTimeField(auto) | Date et heure de la détection |
| `zone_cadastrale` | ForeignKey(ZoneCadastrale, null) | Zone cadastrale intersectée (null si hors cadastre) |
| `geometry_geojson` | TextField | Géométrie en GeoJSON string |
| `ndbi_t1` | FloatField(null) | NDBI médiane à T1 (avant construction) |
| `ndbi_t2` | FloatField(null) | NDBI médiane à T2 (après construction) |
| `bsi_value` | FloatField(null) | BSI médiane à T2 |
| `surface_m2` | FloatField(null) | Surface estimée en m² |
| `confidence` | FloatField(default=0.5) | Score de confiance global [0.0 → 1.0] |
| `present_in_microsoft` | BooleanField(False) | Bâtiment Google V3 connu ici |
| `present_in_t1_sentinel` | BooleanField(False) | Bâti déjà présent à T1 |
| `status` | CharField(30) | `infraction_zonage`, `sous_condition`, `conforme`, `surveillance_preventive` |
| `alert_level` | CharField(20) | `rouge`, `orange`, `vert`, `veille` |
| `verification_required` | BooleanField(True) | Vérification terrain recommandée |
| `statut_traitement` | CharField(20) | `en_attente`, `en_cours`, `confirme`, `faux_positif`, `archive` |
| `traitee_par` | ForeignKey(User, null) | Agent Django traitant |
| `commentaire_terrain` | TextField(blank) | Commentaire de l'agent |
| `date_traitement` | DateTimeField(null) | Date de traitement |

**Méthode `get_centroid_coordinates()`** : extrait le centroïde de la géométrie GeoJSON → retourne `(latitude, longitude)`. ✅ **CORRIGÉ (L1)** : `except Exception: pass` remplacé par `except Exception as e: logger.warning(...)` — les erreurs sont maintenant loguées au niveau WARNING avec l'id de la détection.

**Propriétés `latitude` et `longitude`** : appels directs à `get_centroid_coordinates()`.

**Index définis sur :** `status`, `alert_level`, `date_detection`, `statut_traitement`.

---

#### `module1_urbanisme/admin.py`

**Rôle :** Enregistre les 4 modèles dans l'interface d'administration Django avec support des cartes géographiques interactives (`GISModelAdmin`).

- `ZoneCadastraleAdmin` : list_display = [zone_id, name, zone_type, buildable_status]. list_filter = [buildable_status, zone_type]. search_fields = [zone_id, name].
- `MicrosoftFootprintAdmin` : list_display = [source_file, source, date_reference, confidence_score]. Carte interactive via GISModelAdmin.
- `DetectionConstructionAdmin` : list_display = [date_detection, status, alert_level, confidence, surface_m2, statut_traitement]. list_filter = [status, alert_level, statut_traitement].
- `ImageSatelliteAdmin` : list_display = [date_acquisition, satellite, processed].

---

#### `module1_urbanisme/urls.py`

**Rôle :** Routeur API REST v1 via `DefaultRouter` sur le préfixe `api/v1/`.

| URL | ViewSet | Description |
|---|---|---|
| `api/v1/zones-cadastrales/` | ZoneCadastraleViewSet | Lecture seule |
| `api/v1/images-satellite/` | ImageSatelliteViewSet | Lecture seule |
| `api/v1/microsoft-footprints/` | MicrosoftFootprintViewSet | Lecture seule |
| `api/v1/detections/` | DetectionConstructionViewSet | CRUD complet |
| `api/v1/detections/{id}/traiter/` | Action traiter (PATCH) | Mise à jour statut par agent |
| `api/v1/detections/statistics/` | Action statistics (GET) | Statistiques globales JSON |
| `api/v1/detections/alertes_rouges/` | Action alertes_rouges (GET) | status=infraction_zonage |
| `api/v1/detections/alertes_orange/` | Action alertes_orange (GET) | status=sous_condition |
| `api/v1/detections/en_attente/` | Action en_attente (GET) | statut_traitement=en_attente |
| `api/v1/dashboard/resume/` | DashboardViewSet (GET) | Résumé agrégé |

---

#### `module1_urbanisme/urls_web.py`

**Rôle :** Routeur pour les pages HTML de l'interface utilisateur.

| URL | Vue | Description |
|---|---|---|
| `/` | `dashboard` | Tableau de bord principal |
| `/detections/` | `detections_list` | Liste filtrée des détections |
| `/detections/<int:pk>/` | `detection_detail` | Détail avec carte |
| `/zones/` | `zones_cadastrales` | Liste des zones |
| `/zones/<str:zone_id>/` | `zone_detail` | Détail zone |
| `/api/statistics/` | `api_statistics` | JSON stats (pour graphiques) |
| `/api/detections-geojson/` | `api_detections_geojson` | GeoJSON détections (Leaflet) |
| `/api/zones-geojson/` | `api_zones_geojson` | GeoJSON zones (Leaflet) |

---

#### `module1_urbanisme/urls_simple.py`

**Rôle :** Routeur API v2 simplifié, créé pour contourner des problèmes de sérialisation. Expose `DetectionSimpleViewSet` sur `api/v2/detections-simple/`.
✅ **CORRIGÉ (D4)** : `urls_simple` désormais monté sur le préfixe `"api/v2/"` dans `config/urls.py` — supprime l'ambiguïté de routage avec `urls.py` (`api/v1/`).
✅ **CORRIGÉ (D8)** : `get_priority_score` extrait en fonction standalone `compute_priority_score(obj)` dans `serializers.py`. `serializers_simple.py` l'importe au lieu de dupliquer la logique.

---

#### `module1_urbanisme/views.py`

**Rôle :** Vues API REST complètes via Django REST Framework. CRUD sur les 4 modèles avec filtrage et actions personnalisées.

*`ZoneCadastraleViewSet(ReadOnlyModelViewSet)` :* Filtrage sur `buildable_status`, `zone_type`. Recherche sur `name`, `zone_id`.

*`ImageSatelliteViewSet(ReadOnlyModelViewSet)` :* Filtrage sur `satellite`, `processed`.

*`MicrosoftFootprintViewSet(ReadOnlyModelViewSet)` :* Filtrage sur `source_file`.

*`DetectionConstructionViewSet(ModelViewSet)` :* CRUD complet. Filtrage sur `status`, `alert_level`, `statut_traitement`, `zone_cadastrale__zone_id`. Actions :
- `traiter(PATCH)` : Nécessite `IsAuthenticated`. Met à jour `statut_traitement`, `commentaire_terrain`, `traitee_par` (utilisateur connecté), `date_traitement`.
- `statistics(GET)` : Agrège par status et alert_level.
- `alertes_rouges(GET)` : Filtre `status='infraction_zonage'`, tri par confiance décroissante.
- `alertes_orange(GET)` : Filtre `status='sous_condition'`.
- `en_attente(GET)` : Filtre `statut_traitement='en_attente'`.

*`DashboardViewSet(ViewSet)` :* Action `resume(GET)` : alertes_par_niveau, detections_par_statut, zones_plus_actives (top 5).

✅ **CORRIGÉ (L3)** : la clé aggregate de `statistics()` est renommée `detections_sous_condition`, alignée avec `StatisticsSerializer` et `views_web.py`.

---

#### `module1_urbanisme/views_web.py`

**Rôle :** Vues Django classiques (non-REST) pour l'interface HTML. Génère les pages du tableau de bord, liste des détections, détails, zones cadastrales. Fournit les endpoints JSON pour les cartes Leaflet.

*`dashboard(request)` :* Calcule les statistiques globales via `aggregate(Count(...))`. Charge les 10 dernières détections. Retourne le contexte au template `dashboard.html`.

*`detections_list(request)` :* Filtre par `status` et `alert_level` via paramètres GET.

*`detection_detail(request, pk)` :* Charge une détection avec `select_related('zone_cadastrale')`. Parse la géométrie GeoJSON pour extraire le centroïde.

*`zones_cadastrales(request)` :* Charge toutes les zones avec `annotate(nb_detections=Count('detections'))`.

*`api_statistics(request)` :* `JsonResponse` avec toutes les statistiques agrégées.

*`api_detections_geojson(request)` :* `FeatureCollection` GeoJSON avec propriétés : status, alert_level, NDBI, surface, confiance, alert_label_emoji, lat/lon, zone_id, zone_name.

*`api_zones_geojson(request)` :* `FeatureCollection` GeoJSON des zones. Couleur par `buildable_status` : forbidden→`#dc3545`, conditional→`#fd7e14`, buildable→`#28a745`.

✅ **CORRIGÉ (A10)** : `alertes_orange` filtre sur `status='sous_condition'`. `StatisticsSerializer` expose `detections_sous_condition`. Compteur orange API v1 opérationnel.

---

#### `module1_urbanisme/views_simple.py`

**Rôle :** ViewSet lecture-seule simplifié, créé comme contournement d'erreurs de sérialisation.
✅ **CORRIGÉ (D8 partiel)** : logique de scoring (`compute_priority_score`) extraite et partagée avec `views.py` via import. Duplication structurelle résiduelle documentée comme dette technique acceptable.

---

#### `module1_urbanisme/serializers.py`

**Rôle :** Convertit les objets modèles Python en JSON pour l'API REST v1. Inclut des champs calculés, de la validation, et des méthodes de scoring.

*`ZoneCadastraleSerializer` :* Expose `geometry_geojson` (propriété du modèle) au lieu du champ PostGIS brut. Champs : id, zone_id, name, zone_type, buildable_status, geometry_geojson, metadata.

*`ImageSatelliteSerializer` :* Tous les champs du modèle.

*`MicrosoftFootprintSerializer` :* Champs : id, geometry_geojson, source_file, source, date_reference.

*`DetectionConstructionSerializer` :* Le plus complexe. Champs calculés :
- `priority_score` (0-100) : infraction_zonage→+80, sous_condition→+45, surveillance_preventive→+20. Bonus delta_ndbi > 0.4 → +15, > 0.25 → +8. Bonus surface > 500m² → +5. Plafonné à 100.
- `alert_label` : `"🔴 Infraction au Zonage"`, `"🟠 Inspection Requise"`, `"🟢 Développement Conforme"`, `"🔵 Surveillance Préventive"`.
- `status_display`, `alert_level_display` via `get_*_display()`.
- `traitee_par_username` via `source='traitee_par.username'`.
- `latitude`, `longitude` via propriétés du modèle.

*`DetectionCreateSerializer` :* Champs minimaux pour création programmatique.

*`DetectionUpdateSerializer` :* Uniquement `statut_traitement` et `commentaire_terrain`. Validation : si `statut_traitement` ∈ {`confirme`, `faux_positif`}, le commentaire est **obligatoire** (sinon `ValidationError`).

*`StatisticsSerializer` :* Champs IntegerField pour les statistiques agrégées.

✅ **CORRIGÉ (L3)** : `StatisticsSerializer` déclare maintenant `detections_sous_condition`, cohérent avec `views.py` et `views_web.py`.

---

#### `module1_urbanisme/serializers_simple.py`

**Rôle :** Serializers allégés sans champs géométriques pour l'API v2.

*`ZoneCadastraleSimpleSerializer` :* Champs : id, zone_id, name, zone_type, buildable_status (sans geometry).

*`DetectionConstructionSimpleSerializer` :* Expose zone_cadastrale (nested), status_display, alert_level_display, priority_score, alert_label.

✅ **CORRIGÉ (D8)** : `get_priority_score()` supprimée de `serializers_simple.py`. Remplacée par un import de `compute_priority_score(obj)` depuis `serializers.py`. Aucune duplication de logique.

---

#### `module1_urbanisme/gee_split_app.js`

**Rôle :** Script JavaScript à déployer dans l'éditeur Google Earth Engine (code.earthengine.google.com). Crée une application GEE publique de type split-screen pour comparer visuellement T1 (2024) et T2 (2025) à la position d'une détection CIV-EYE.

**Contenu (67 lignes) :**
1. Lecture des paramètres `lat` et `lon` depuis l'URL (appel via iframe depuis `detection_detail.html`)
2. Fonction `getCloudFreeImage(year)` : composite médian Sentinel-2 L2A saison sèche (Jan→Mar), filtré `CLOUDY_PIXEL_PERCENTAGE < 20`, masqué SCL (classes 3,8,9,10 exclus)
3. Deux cartes `ui.Map()` : gauche T1 (2024), droite T2 (2025)
4. `ui.Map.Linker` : synchronisation zoom et déplacements
5. Marqueur rouge sur la position de la détection
6. `ui.SplitPanel` avec wipe horizontal

**Usage :** Coller dans code.earthengine.google.com → Publier comme "App" → Copier l'URL → Remplacer le placeholder `VotreCompteGEE` dans `detection_detail.html`.

---

#### `module1_urbanisme/tests.py`

**Rôle :** 5 tests unitaires Django couvrant les composants critiques du pipeline. Exécutables via `python manage.py test module1_urbanisme`.

| Test | Ce qu'il vérifie |
|---|---|
| `NDBICalculatorTest.test_ndbi_values_in_range` | NDBI retourne uniquement des valeurs dans `[-1.0, 1.0]` |
| `ChangeDetectionTest.test_new_construction_detected` | `detect_changes()` détecte les pixels avec NDBI 0.05→0.35 et 0.1→0.30 |
| `BUICalculationTest.test_bui_filters_vegetation` | BUI > 0 pour vrai bâtiment, BUI < 0 pour végétation dense |
| `MinSurfaceRejectionTest.test_small_detection_rejected` | `verify_detection(surface_m2=100.0)` retourne `None` (< 200m²) |
| `ThresholdCoherenceTest.test_ndbi_threshold_coherence` | `threshold_built == 0.2` ET ≥ 0.10 (seuil CIV) |

---

### 📁 module1_urbanisme/pipeline/

---

#### `pipeline/__init__.py`

**Rôle :** Marque le dossier comme package Python et expose les classes principales pour l'import direct depuis l'extérieur du package.

**Exports :**
```python
from .ndbi_calculator import NDBICalculator
from .ai_detector import AIDetector
from .verification_4_couches import Verification4Couches, DetectionPipeline
from .sentinel_data_fetcher import SentinelDataFetcher
```

---

#### `pipeline/ndbi_calculator.py`

**Rôle :** Cœur algorithmique du calcul des indices spectraux sur les images satellites Sentinel-2. Contient la classe `NDBICalculator` et des fonctions utilitaires standalone. C'est le module le plus utilisé du projet (622 lignes).

**Appelle :** `rasterio` (lecture des TIFF et rééchantillonnage), `numpy` (calcul matriciel), `scipy.ndimage` (labellisation des régions connexes).
**Est appelé par :** `run_detection.py`, `ai_detector.py`, `tests.py`, `test_pipeline_validation.py`, `test_audit.py`.

**Attributs de la classe :**
```python
self.threshold_built = 0.2   # Seuil NDBI pour détecter du bâti
self.threshold_soil  = 0.15  # Seuil BSI pour détecter du sol nu (terrassement)
```

**Méthodes détaillées :**

*`calculate_ndbi(b08_path, b11_path) → ndarray float64` :*
- Ouvre B08 (NIR, 10m/pixel) et B11 (SWIR, 20m/pixel) avec rasterio
- Si les shapes diffèrent : rééchantillonne B11 vers la résolution de B08 via `rasterio.warp.reproject(Resampling.bilinear)`
- Formule : `NDBI = (B11 - B08) / (B11 + B08 + ε)` (ε = 1e-10 pour éviter division par zéro)
- Clip des valeurs dans `[-1.0, 1.0]`
- Retourne un ndarray 2D de la même taille que B08

*`calculate_bsi(b04_path, b08_path, b11_path, b02_path=None) → ndarray float64` :*
- ✅ **CORRIGÉ (D9)** : Formule complète Zha et al. 2003 activée si `b02_path` fourni : `BSI = ((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02))`
- Fallback automatique sans B02 : `BSI_approx = (B11-B08)/(B11+B08)`
- Label de formule loggé (`BSI_complet` ou `BSI_approx`) pour traçabilité

*`calculate_ndvi(b04_path, b08_path) → ndarray float64` :*
- Formule : `NDVI = (B08 - B04) / (B08 + B04 + ε)`
- Clip dans `[-1.0, 1.0]`

*`calculate_bui(ndbi, ndvi) → ndarray float64` :*
- Formule : `BUI = NDBI - NDVI`
- BUI > 0 → bâti (signal NDBI domine)
- BUI < 0 → végétation (signal NDVI domine) → filtre faux positifs constructions sous arbres

*`detect_changes(ndbi_t1, ndbi_t2, bsi_t2=None, ndvi_t2=None, bui_threshold=0.05) → Dict` :*
- `new_constructions` : pixels où `(ndbi_t1 <= threshold_built) & (ndbi_t2 > threshold_built)`
- `soil_activity` : pixels où `(bsi_t2 > threshold_soil) & ~new_constructions`
- `demolished` : pixels où `(ndbi_t1 > 0.25) & (ndbi_t2 < 0.05)` ← CORRECTIF L1 (détection démolitions)
- Masque eau proxy : `(ndbi_t2 < -0.15)` → exclusion des pixels aquatiques sans B03
- Masque NDVI végétation : si `ndvi_t2 > 0.4` → exclusion ← CORRECTIF L3
- `all_changes = new_constructions | soil_activity | demolished`
- Retourne : `{'new_constructions': mask, 'soil_activity': mask, 'demolished': mask, 'all_changes': mask}`

*`extract_change_regions(change_mask, min_size=2, max_size=500) → list` :*
- `scipy.ndimage.label(change_mask)` → composantes connexes
- Pour chaque composante de taille ∈ [min_size, max_size] pixels : extrait label, size_pixels, bbox (row_min, col_min, row_max, col_max), centroïde (row, col)
- min_size=2 capture les petites maisons (~50m²), max_size=500 évite les faux positifs massifs

*`apply_scl_mask(array, scl_path, invalid_classes=[3,6,8,9,10]) → ndarray` :*
- Ouvre le fichier SCL (Scene Classification Layer) Sentinel-2
- Rééchantillonne SCL si nécessaire (20m → 10m)
- Classes invalides masquées par NaN : 3=ombre nuage, 6=eau, 8=nuage moyen, 9=nuage dense, 10=cirrus

*`compute_confidence(ndbi_t1, ndbi_t2, bsi, surface_px, cloud_cover_pct=0.0) → float` :*
- Formule pondérée :
  - 40% : `delta_ndbi = ndbi_t2 - ndbi_t1` normalisé sur [0, 0.6]
  - 20% : `bsi` normalisé sur [0, 0.5]
  - 20% : `surface_px` normalisé logarithmiquement
  - 20% : `(1 - cloud_cover_pct / 100)` (pénalise les zones nuageuses)
- Retourne float dans [0.0, 1.0]

*`get_cloud_percentage(scl_path) → float` :*
- Lit le fichier SCL et calcule le pourcentage de pixels dans les classes nuageuses (8, 9, 10)

*`_resample_to_match(source_src, target_src) → ndarray` :*
- Rééchantillonnage bilinéaire via `rasterio.warp.reproject` pour aligner deux rasters de résolutions différentes

**Fonctions utilitaires standalone :**
- `calculate_ndbi_for_period(b08_path, b11_path)` → alias publique de `NDBICalculator().calculate_ndbi()`
- `calculate_bsi_for_period(b04_path, b08_path, b11_path)` → alias publique
- `detect_construction_changes(b08_t1, b11_t1, b04_t2, b08_t2, b11_t2)` → pipeline complet sans DB

---

#### `pipeline/ai_detector.py`

**Rôle :** Détecteur IA non-supervisé par K-Means Clustering spectral. Analyse les pixels combinant NDBI, NDVI, et texture Sobel pour identifier les classes de bâti. Mode activé via `--use-ai` dans `run_detection.py`.

**Appelle :** `numpy`, `cv2` (OpenCV), `sklearn.cluster.MiniBatchKMeans`.
**Est appelé par :** `run_detection.py` dans `calculate_ai_pipeline()`.

**Méthodes de `AIDetector` :**

*`normalize(band) → ndarray uint8` :*
- Normalise un array numpy float entre 0 et 255 pour OpenCV

*`compute_features(b04, b08, b11) → ndarray(H, W, 3)` :*
- Feature 1 (NDBI) : `(b11 - b08) / (b11 + b08 + ε)` normalisé
- Feature 2 (NDVI) : `(b08 - b04) / (b08 + b04 + ε)` normalisé
- Feature 3 (Texture Sobel) : `cv2.Sobel` sur B08 normalisé uint8 → gradient magnitude = texture architecturale
- Stack des 3 features → ndarray (H, W, 3)

*`predict_buildings(b04, b08, b11) → (mask_uint8, segmented)` :*
- Reshape (H×W, 3) pour MiniBatchKMeans avec `n_clusters=4`
- Pour chaque cluster : calcule un score bâti `B40 = mean(NDBI)×1.2 - mean(NDVI) + mean(Texture)×0.7`
- Pénalise les clusters avec NDBI moyen < -0.05 (eau/végétation dense)
- Identifie le(s) cluster(s) avec le score B40 le plus élevé comme "bâti"
- Applique `cv2.morphologyEx(MORPH_OPEN)` puis `MORPH_CLOSE` avec kernel 3×3 pour nettoyer le masque
- ✅ **B39 NON-BUG — Compensé par conception** : K-Means analyse T1 et T2 indépendamment, mais le pipeline ne compare JAMAIS les numéros de clusters. Il identifie le cluster "bâti" par score B40 indépendamment sur chaque image, produit deux masques binaires (0/1), puis compare `(mask_t2==1) & (mask_t1==0)`. `random_state=42` assure la reproductibilité.

*`extract_clusters_regions(model_mask, min_size=2) → list` :*
- `cv2.connectedComponentsWithStats(mask_uint8)` → liste de régions avec statistiques (label, aire, bbox, centroïde)

---

#### `pipeline/verification_4_couches.py`

**Rôle :** Logique de vérification et classification des détections brutes du pipeline en 4 couches successives. Détermine si une détection est une vraie infraction ou un faux positif. Module le plus complexe du pipeline (611 lignes).

**Appelle :** `models.py` (ZoneCadastrale, MicrosoftFootprint, DetectionConstruction), `django.contrib.gis.geos.GEOSGeometry`, `json`.
**Est appelé par :** `run_detection.py` via `DetectionPipeline.process_detection_regions()`.

**Constantes :**
```python
MIN_SURFACE_M2 = 200          # Surface minimale d'une construction détectable à 10m/px
GOOGLE_SEARCH_RADIUS_M = 15   # Rayon de recherche PostGIS en mètres
CIV_NDBI_THRESHOLD = 0.10     # Seuil NDBI calibré pour matériaux ivoiriens (tôle, béton brut)
```

**Classe `Verification4Couches` :**

*`verify_detection(geometry_geojson, ndbi_t1_val, ndbi_t2_val, bsi_val, change_type, confidence_ia, surface_m2) → Dict | None` :*

Pipeline complet des 4 couches :

**CAS 0 — Filtre surface minimale :**
Si `surface_m2 < MIN_SURFACE_M2` → `return None` (rejeté)
Raison : à 10m/pixel de résolution, une surface < 200m² (2 pixels × 10m × 10m) ne peut pas être une construction fiable.

**Couche 1 — Vérification Google Open Buildings :**
`_check_google_buildings(geometry_geojson)` :
- Calcule le centroïde du polygone détecté
- Requête PostGIS : `MicrosoftFootprint.objects.filter(geometry__dwithin=(centroid_geos, radius_degrees)).order_by('-confidence_score')`
- 7 cas logiques selon résultat :
  - Aucun résultat → `NOUVELLE_CONSTRUCTION_POSSIBLE` (poursuite)
  - Confidence < 0.65 → `EXISTENCE_DOUTEUSE` (poursuite avec confiance réduite)
  - 0.65 ≤ confidence < 0.70 → `VERIFICATION_REQUISE` (poursuite, flag verification_required=True)
  - 0.70 ≤ confidence < 0.75 → `PROBABLEMENT_PRE_EXISTANT` (poursuite avec avertissement)
  - confidence ≥ 0.75 → `FAUX_POSITIF_PRE_EXISTANT` → `return None` (**Limitation P4 : nécessite Google Temporal V1 API pour distinguer construction récente vs pré-existante**)
  - Source `Google_Temporal_V1` avec date > T1 → `NOUVELLE_CONSTRUCTION_CONFIRMEE` (poursuite renforcée)
  - Bâtiment Google très grand (area > 2000m²) → `SURVEILLANCE_PREVENTIVE`

**Couche 2 — Vérification NDBI T1 (bâti historique) :**
Si `ndbi_t1_val > threshold_built × 1.5` → `return None`
Raison : si NDBI T1 est déjà très élevé, le bâtiment existait probablement avant T1. Ce n'est pas une nouvelle construction.

**Couche 3 — Validation cohérence spectrale (seuils CIV) :**
`_is_valid_change(ndbi_t1, ndbi_t2, change_type, confidence_ia)` :
- Seuil calibré pour la Côte d'Ivoire : `CIV_NDBI_THRESHOLD = 0.10` (vs 0.35 en Europe tempérée)
- Raison du seuil bas : les matériaux locaux (tôle ondulée galvanisée, béton non peint) ont un fort signal SWIR même à faible NDBI
- Pour `new_construction` : vérifie `ndbi_t2 >= CIV_NDBI_THRESHOLD` ET `ndbi_t2 > ndbi_t1 + 0.05`
- Pour `soil_activity` : vérifie BSI significatif
- Pour `demolition` : vérifie `ndbi_t1 > 0.20` ET `ndbi_t2 < 0.05`

**Couche 4 — Classification légale par le cadastre :**
`_classify_by_zoning(geometry_geojson, change_type, bsi_val, present_microsoft)` :
- Tentative 1 : `ZoneCadastrale.objects.filter(geometry__contains=centroid_geos)` (ST_Contains)
- Tentative 2 (fallback) : `ZoneCadastrale.objects.filter(geometry__intersects=polygon_geos)` (ST_Intersects)
- Si aucune zone : classification `hors_cadastre` avec alert_level `veille`
- Selon `buildable_status` de la zone :
  - `forbidden` → `_classify_new_construction()` → status `infraction_zonage`, alert_level `rouge`
  - `conditional` → `_classify_new_construction()` → status `sous_condition`, alert_level `orange`
  - `buildable` → `_classify_new_construction()` → status `conforme`, alert_level `vert`
- Types spéciaux :
  - `soil_activity` → `_classify_soil_activity()` : exclut `harbour`, `flood_prone`, `water`, `airport` (faux positifs lagune) → `veille`
  - `demolition` → `_classify_demolition()` → alert_level `orange` systématique

**Classe `DetectionPipeline` :**

*`process_detection_regions(regions, image_metadata) → list[DetectionConstruction]` :*
- Itère chaque région issue de `extract_change_regions()`
- Appelle `verify_detection()` pour chaque région
- Si classification non nulle : appelle `_create_detection_record()`
- Tout dans `transaction.atomic()`

*`_extract_region_values(region, image_metadata) → Dict` :*
- Extrait ndbi_t1, ndbi_t2, bsi depuis le dict région (valeurs médiane calculées sur la bbox)

*`_create_detection_record(region, classification, ndbi_values) → DetectionConstruction` :*
- Construit la géométrie PostGIS via `GEOSGeometry(json.dumps(region['geojson']))`
- `DetectionConstruction.objects.create(...)` avec toutes les données de classification

---

#### `pipeline/sentinel_data_fetcher.py`

**Rôle :** Acquisition multi-source des données Sentinel-2 L2A. Essaie 3 sources en cascade (Sentinel Hub → CDSE Copernicus → Microsoft Planetary Computer) et retourne les bandes spectrales comme arrays numpy normalisés. Module Phase 3 du pipeline (476 lignes).

**Appelle :** `sentinelhub`, `pystac_client`, `planetary_computer`, `rasterio`, `numpy`, `os.getenv`.
**Est appelé par :** `import_sentinel_api.py`.

**Constantes :**
```python
TREICHVILLE_BBOX = {
    "min_lon": -4.03001, "min_lat": 5.28501,
    "max_lon": -3.97301, "max_lat": 5.32053
}
BAND_RESOLUTION = {
    "B02": 10, "B03": 10, "B04": 10, "B08": 10,
    "B11": 20, "B12": 20, "SCL": 20
}
```

**Méthodes de `SentinelDataFetcher` :**

*`__init__()` :*
- Teste la disponibilité des 3 sources via les variables d'environnement
- `_sh_available` : True si `SENTINEL_HUB_CLIENT_ID` et `SENTINEL_HUB_CLIENT_SECRET` sont définis
- `_cdse_available` : True si le catalogue STAC CDSE est accessible (pas de clé requise)
- `_pc_available` : True si `MICROSOFT_PC_API_KEY` est défini

*`get_bands_for_date(target_date, bands, bbox, max_cloud_cover=20, date_window_days=15) → Dict[str, ndarray]` :*
- API principale. Retourne un dict `{"B04": array, "B08": array, "B11": array, "SCL": array}` en float32 normalisés [0,1]
- Essaie Sentinel Hub si disponible, puis CDSE, puis Planetary Computer
- Fenêtre temporelle : ±`date_window_days` autour de la date cible

*`_fetch_sentinel_hub(date_from, date_to, bands, bbox)` :*
- Configure un evalscript Sentinel Hub qui calcule le composite médian (filtre nuages côté serveur avec `leastCC`)
- Normalise les DN : `array / 10000.0` pour passer de [0,10000] à [0,1]

*`_fetch_cdse(date_from, date_to, bands, bbox, max_cloud_cover)` :*
- Client STAC sur `https://catalogue.dataspace.copernicus.eu/stac`
- Recherche les items Sentinel-2 L2A avec CLOUD_COVER_ASSESSMENT < max_cloud_cover
- Sélectionne l'item avec le moins de nuages
- Lecture directe des COG (Cloud Optimized GeoTIFF) via `rasterio.open(signed_url)` avec fenêtre bbox

*`_fetch_planetary_computer(date_from, date_to, bands, bbox)` :*
- Client STAC via `planetary_computer.sign_url(item.assets[band].href)`
- Lecture des COG signés

*`get_t1_and_t2_bands(date_t1, date_t2) → tuple` :*
- Appelle `get_bands_for_date()` pour chaque date
✅ **CORRIGÉ (D12)** : `date_t1` et `date_t2` sont maintenant des paramètres **obligatoires** (sans valeur par défaut). Lève `ValueError` explicite si absent : *"get_t1_and_t2_bands : date_t1 et date_t2 sont obligatoires."*
✅ **CORRIGÉ (CDSE)** : `_fetch_cdse` mis à jour — collection `"SENTINEL-2"` → `"sentinel-2-l2a"`, suppression paramètre `query` non supporté.

*`status() → Dict` :*
- Retourne l'état des 3 sources : `{"sentinel_hub": bool, "cdse": bool, "planetary_computer": bool}`

---

#### `pipeline/gee_composite.py`

**Rôle :** Compositeur Google Earth Engine pour créer des images médianes sans nuages sur la saison sèche. Alternative haute qualité à CDSE pour la Phase 4 (compositing multi-temporel).

**Appelle :** `earthengine-api` (`ee`), `requests`, `numpy`.
**Est appelé par :** `run_detection.py` (optionnel, non activé par défaut).

**Méthodes de `GEECompositor` :**

*`_init_gee()` :*
- `ee.Initialize(project=os.getenv('GEE_PROJECT_ID'))` — nécessite `earthengine authenticate` exécuté préalablement dans le terminal

*`get_composite(year, bands, bbox, max_cloud_cover=20) → Dict[str, ndarray]` :*
- Collection `COPERNICUS/S2_SR_HARMONIZED`, filtrée sur la saison sèche (Nov(year-1) → Mar(year))
- `_mask_clouds_s2()` : masque avec SCL (classes 3,8,9,10)
- `.median()` : composite médian sur toute la période (image synthétique "parfaite")
- Téléchargement via `getDownloadURL`
- ✅ **CORRIGÉ (B2)** : `format: "NPY"` remplacé par `"GEO_TIFF"` (format valide de l'API GEE) · parsing adapté avec `rasterio.open()` au lieu de `np.load()`.

*`get_t1_and_t2_composites(year_t1, year_t2) → tuple` :*
- Récupère les composites pour T1 et T2

*`status() → Dict` :*
- Teste la disponibilité de GEE

---

#### `pipeline/api_health_checker.py`

**Rôle :** Diagnostique la disponibilité de toutes les sources de données au démarrage de `run_detection`. Bloque l'exécution si aucune source n'est accessible.

**Appelle :** `os.getenv`, `urllib.request`, API earthengine.
**Est appelé par :** `run_detection.py` à chaque lancement (méthode `handle()`, première étape).

**Méthodes de `APIHealthChecker` :**

*`run_all_checks() → Dict` :*
- Lance les 6 vérifications en séquence
- Affiche un rapport structuré avec indicateurs visuels ✅/⚠️/❌

*`_check_local_tiff_files() → bool` :*
- Vérifie la présence de sous-dossiers date dans `sentinel_api_exports/`
- Pour chaque dossier date : vérifie la présence des bandes B04, B08, B11
- ✅ **CORRIGÉ (D13)** : Test d'intégrité ajouté — `rasterio.open(first_tif)` + `src.shape` vérifie que le header TIFF est lisible. Fichiers corrompus signalés en ⚠️ sans bloquer le pipeline.

*`_check_sentinel_hub() → bool` :*
- Test OAuth2 réel sur `https://services.sentinel-hub.com/oauth/token`
- Vérifie que les credentials retournent un access_token valide

*`_check_cdse_stac() → bool` :*
- Test HTTP GET sur le catalogue STAC CDSE public
- Ne nécessite aucune clé API

*`_check_microsoft_planetary_computer() → bool` :*
- Test avec la clé `MICROSOFT_PC_API_KEY`

*`_check_google_earth_engine() → bool` :*
- Test `ee.Initialize(project=GEE_PROJECT_ID)`

*`_check_huggingface_api() → bool` :*
- Test GET sur `https://huggingface.co/api/whoami-v2` avec le token

*`assert_minimum_viable()` :*
- Lève `RuntimeError: ❌ AUCUNE SOURCE DE DONNÉES DISPONIBLE` si aucune source n'est accessible
- Avertit si < 2 images `ImageSatellite` sont présentes en base (insuffisant pour la comparaison T1/T2)

---

#### `pipeline/b03_downloader.py`

**Rôle :** Télécharge automatiquement la bande B03 (Vert, 10m/pixel) depuis CDSE Copernicus (gratuit, sans clé API) pour activer le masque eau NDWI (Correction L2).

**Méthodes :**

*`download_b03_cdse(date_from, date_to, output_dir) → str | None` :*
- Catalogue STAC CDSE collection `"sentinel-2-l2a"` ✅ **CORRIGÉ** (ancien nom `SENTINEL-2` retournait 0 résultats)
- Filtrage nuages côté Python (≤ 80%) — paramètre `query` STAC non supporté par CDSE
- URL S3 `s3://eodata/` convertie en HTTPS `https://eodata.dataspace.copernicus.eu/` ✅ **CORRIGÉ** (S3 retournait `AccessDenied`)
- Lecture COG B03 via `rasterio.Env(GDAL_HTTP_UNSAFESSL='YES')` + `rasterio.open(https_url)`
- Normalise : `array / 10000.0` — sauvegarde `B03_{date}.tif` dans `sentinel_api_exports/{date}/`
- Vérifie l'existence du fichier avant téléchargement (idempotent)
- Retourne le chemin du fichier créé, ou `None` si erreur HTTP (403)

*`calculate_ndwi_from_paths(b03_path, b08_path) → ndarray | None` :*
- Formule : `NDWI = (B03 - B08) / (B03 + B08 + ε)`
- Valeurs > 0 → eau (lagune, rivière) → masqués dans le pipeline
- Retourne `None` si `b03_path` est `None` ou inexistant

---

#### `pipeline/b03_synthesizer.py`

**Rôle :** Génère une approximation synthétique de la bande B03 (Vert) à partir de B04 (Rouge) et B08 (NIR) quand B03 réelle n'est pas disponible.

**Méthode `synthesize_b03(b04_path, b08_path, output_path=None) → str | None` :**
- Si `output_path` non spécifié : génère le chemin automatiquement dans le même répertoire que B04, nommé `B03_synth_{date}.tif`
- Vérification idempotente : si le fichier existe déjà, retourne son chemin sans recalculer
- Formule Delegido et al. (2011) :
  ```
  B03_synthetic = clip(0.75 × B04 + 0.25 × B08, 0.0, 1.0)
  ```
- Validation B42 : avertissement si `B04.max() > 1.5` ou `B08.max() > 1.5` (données non normalisées)
- Rééchantillonnage bilinéaire de B08 si les shapes diffèrent
- Sauvegarde en TIFF float32 avec le profil de B04

**Limitations documentées :**
- Approximation spectrale — B03 réelle donne de meilleurs résultats pour NDWI
- Suffisante pour le masque eau et l'alimentation de TinyCD en pseudo-RGB

---

#### `pipeline/deep_learning_detector.py`

**Rôle :** Détecteur Deep Learning basé sur TinyCD (réseau siamois PyTorch). Mode EXPÉRIMENTAL — poids entraînés sur données à 0.5m/pixel non adaptées aux données Sentinel-2 à 10m/pixel.

**Appelle :** `torch`, `torchvision`, `cv2`, `numpy`, `tinycd_models.change_classifier.ChangeClassifier`.
**Est appelé par :** `run_detection.py` (mode `--use-tinycd`).

**Attributs de `DeepLearningDetector` :**
```python
self.weights_path = os.path.join(BASE_DIR, "data_use", "weights", "model_weights.pth")
self.is_ready = False    # Mis à True uniquement si les poids sont chargés avec succès
self.device = "cuda" si torch.cuda.is_available() sinon "cpu"
```

**Méthodes :**

*`__init__(model_version="tinycd")` :*
- Vérifie l'existence de `model_weights.pth`
- Si présent : charge le modèle et met `is_ready = True`
- Si absent : log un avertissement et laisse `is_ready = False` — ✅ **CORRIGÉ P9** : `run_detection.py` lève un `CommandError` explicite si `--use-tinycd` est demandé sans poids

*`_load_model(torch)` :*
- Instancie `ChangeClassifier(bkbn_name="efficientnet_b4", pretrained=False, output_layer_bkbn="3")`
- ✅ **CORRIGÉ B32** : `torch.load(..., weights_only=True)` — évite l'exécution de code arbitraire via pickle. Compteur de clés remappées logé (`{N} clé(s) remappée(s) _mixing._convmix → _convmix`) pour débogage avec de nouveaux poids.
- `strict=False` maintenu : tolère les couches manquantes sans erreur

*`detect(t1_array, t2_array) → ndarray uint8` :*
- Si `is_ready == False` : retourne un masque de zéros — mais ce chemin est bloqué en amont par le `CommandError` de `run_detection.py` (✅ P9)
- Normalisation dynamique : `array = (array - min) / (max - min)` → [0, 1]
- Padding pour obtenir des dimensions multiples de 32 (requis par les couches de convolution)
- Conversion en tenseur PyTorch, ajout dimension batch
- `with torch.no_grad(): output = model(t1_tensor, t2_tensor)`
- Seuillage via `TINYCD_CHANGE_THRESHOLD` : `pred_mask = (output > TINYCD_CHANGE_THRESHOLD).squeeze()...`
- ✅ **CORRIGÉ B33** : seuil extrait en constante nommée `TINYCD_CHANGE_THRESHOLD = 0.30` en tête de fichier. Facile à calibrer quand la vérité terrain ivoirienne sera disponible (données GPS Treichville).

---

#### `pipeline/sentinel1_sar.py`

**Rôle :** Module Sentinel-1 SAR (Radar à Synthèse d'Ouverture) pour la détection anti-nuage. Phase 7 du plan — structuré dans le code mais non fonctionnel (nécessite un token d'entreprise Sentinel Hub payant).

**Constante :**
```python
THRESHOLD_VV = 0.15  # Seuil de rétrodiffusion VV pour détecter un nouveau bâtiment
```

**Fonctions :**

*`evaluate_sar_backscatter_delta(vv_t1, vv_t2, vh_t1, vh_t2) → ndarray` :*
✅ **CORRIGÉ (B1)** : `delta_vv = vv_t2 - vv_t1` ajouté à la ligne 24, avant le calcul du masque. ~~`delta_vv` était utilisé sans jamais être défini → `NameError` immédiat si la fonction était appelée.~~ Cette fonction n'est pas appelée depuis `run_detection.py`, donc le bug n'affectait pas le fonctionnement actuel.

*`fetch_and_evaluate_sar_for_bbox(sh_config, bbox_wgs84, date_t1, date_t2) → Dict` :*
- Retourne toujours `{"sar_detected": False, "delta_vv_db": None, "message": "En attente du token d'entreprise Sentinel Hub pour les bandes S1-GRD."}`
- Fonction stub documentant l'interface future

*`merge_optical_and_sar_masks(optical_mask, sar_mask) → ndarray` :*
- Si les shapes diffèrent : redimensionne `sar_mask` avec `cv2.resize(INTER_NEAREST)`
- Retourne `np.logical_or(optical_mask > 0, sar_mask > 0).astype(np.uint8) * 255`

---

#### `pipeline/huggingface_ai_client.py`

**Rôle :** Système de scoring de validation locale des détections via règles spectrales pondérées. Initialement prévu pour l'API HuggingFace cloud (désactivée — modèles non adaptés au contexte ivoirien), fonctionne entièrement en local.

**Est appelé par :** `run_detection.py` (mode `--use-hf-ai`).

**Constante :**
```python
MODELS_TO_TRY = []  # Vidé volontairement — décision du 22/03/2026
```

**Méthodes de `HuggingFaceAIClient` :**

*`is_available() → bool` :*
- Retourne toujours `True` (mode local toujours disponible)

*`validate_change_detection(ndbi_t1_crop, ndbi_t2_crop, bsi_crop) → float` :*
- Délègue à `_local_ai_score()`

*`_local_ai_score(ndbi_t1, ndbi_t2, bsi) → float` :*
Règles spectrales pondérées (score de base = 0.5) :
- `delta_ndbi_mean > 0.3` → +0.15
- `delta_ndbi_mean > 0.15` → +0.08
- `ndbi_t2_mean > 0.2` → +0.12
- `bsi_mean > 0.1` → +0.10
- Faible dispersion (cohérence spatiale) → +0.05
- Grande surface (> 15 pixels) → +0.05
- Anomalies (valeurs nulles, ndbi_t2 négatif) → −0.15 à −0.20
- Résultat clippé dans [0.1, 0.95]

*`batch_validate(regions, ndbi_t1, ndbi_t2) → list` :*
- Pour chaque région : extrait un crop 10×10 autour du centroïde dans les arrays NDBI
- Calcule `_local_ai_score()` sur le crop
- Met à jour `confidence = confidence × 0.7 + ai_score × 0.3` (pondération 70/30)

---

#### `pipeline/tinycd_models/change_classifier.py`

**Rôle :** Implémentation PyTorch de l'architecture TinyCD (Tiny Change Detection). Réseau siamois qui prend deux images (T1 et T2) et produit une carte de probabilité de changement pixel par pixel.

**Classe `ChangeClassifier(Module)` :**

*`__init__(bkbn_name, pretrained, output_layer_bkbn, freeze_backbone)` :*
- `_backbone` : backbone EfficientNet-B4 partagé (chargé via `_get_backbone()`), tronqué à la couche `output_layer_bkbn` (="3" par défaut)
- `_first_mix` : `MixingMaskAttentionBlock(6, 3, ...)` — fusionne T1 et T2 dès les pixels bruts
- `_mixing_mask` : 3 blocs `MixingMaskAttentionBlock` aux niveaux 1, 2 et un `MixingBlock` au niveau 3
- `_up` : 3 blocs `UpMask(2, ...)` pour l'upsampling décodeur
- `_classify` : `PixelwiseLinear([32,16,8], [16,8,1], Sigmoid())` — sortie probabilité [0,1]

*`forward(ref, test) → Tensor` :*
```
features = _encode(ref, test)
latents = _decode(features)
return _classify(latents)
```

*`_encode(ref, test) → List[Tensor]` :*
- `features[0]` = `_first_mix(ref, test)` sur les images brutes
- Pour chaque couche du backbone : passe ref et test indépendamment
- `features[i]` = `_mixing_mask[i-1](ref_feat, test_feat)` (attention croisée)

*`_decode(features) → Tensor` :*
- Démarre du dernier feature (plus profond)
- Applique successivement les 3 `UpMask` en utilisant les features intermédiaires comme masques multiplicatifs

**Fonction `_get_backbone(bkbn_name, pretrained, output_layer_bkbn, freeze_backbone)` :**
- `torchvision.models.efficientnet_b4(weights="DEFAULT")` → charge le backbone pré-entraîné sur ImageNet
- Découpe aux premières couches jusqu'à `output_layer_bkbn="3"`
- Si `freeze_backbone=True` : `param.requires_grad = False` pour toutes les couches

---

#### `pipeline/tinycd_models/layers.py`

**Rôle :** Briques PyTorch de base de l'architecture TinyCD.

**Classes :**

*`PixelwiseLinear(Module)` :*
- Séquence de convolutions 1×1 (opérations pixel par pixel, sans contexte spatial)
- PReLU entre chaque couche, activation finale configurable (Sigmoid pour la sortie)
- Usage : classification finale et ajustement des canaux

*`MixingBlock(Module)` :*
- Fusionne deux tenseurs T1 et T2 de taille (B, C, H, W) :
  - `stack((x, y), dim=2)` → (B, C, 2, H, W)
  - `reshape → (B, 2C, H, W)` (canaux entrelacés)
  - Convolution groupée (grouped=ch_out) : chaque canal T1 est mixé avec son canal T2 correspondant
- Usage : fusion bi-temporelle légère sans attention

*`MixingMaskAttentionBlock(Module)` :*
- Combine `MixingBlock` (fusion brute) + `PixelwiseLinear` (attention par canal) → masque d'attention
- Si `generate_masked=True` : applique `InstanceNorm2d(mixing_out × mask)` → attention spatiale
- Usage : mécanisme d'attention bi-temporelle pour la détection de changements

*`UpMask(Module)` :*
- Upsample bilinéaire × scale_factor
- Si tenseur `y` fourni : multiplication élément par élément (y est utilisé comme masque/gate)
- Convolution dépth-wise 3×3 (séparable) + PReLU + InstanceNorm2d + Conv 1×1 + PReLU + InstanceNorm2d
- Usage : décodeur avec skip connections multiplicatives

---

### 📁 module1_urbanisme/management/commands/

---

#### `commands/run_detection.py`

**Rôle :** Commande Django principale et chef d'orchestre du pipeline de détection. Lance toutes les étapes de bout en bout depuis la ligne de commande (776 lignes).

**Appelle :** `api_health_checker.py`, `ndbi_calculator.py`, `ai_detector.py`, `deep_learning_detector.py`, `b03_synthesizer.py`, `b03_downloader.py`, `huggingface_ai_client.py`, `sentinel1_sar.py`, `verification_4_couches.py`, `models.ImageSatellite`.
**Est appelé par :** `python manage.py run_detection [options]`

**Arguments CLI :**

| Argument | Défaut | Description |
|---|---|---|
| `--date-t1` | None | Date de l'image T1 (YYYY-MM-DD) |
| `--date-t2` | None | Date de l'image T2 (YYYY-MM-DD) |
| `--threshold-built` | 0.2 | Seuil NDBI pour détecter du bâti |
| `--threshold-soil` | 0.15 | Seuil BSI pour détecter du sol nu |
| `--dry-run` | False | Calcule mais n'écrit pas en base |
| `--min-region-size` | 2 | Taille minimale des régions (pixels) |
| `--use-ai` | False | Active le mode K-Means (AIDetector) |
| `--use-tinycd` | False | Active le mode Deep Learning (TinyCD) |
| `--use-sar` | False | Active le module SAR Sentinel-1 |
| `--use-hf-ai` | False | Active le scoring local HuggingFace |
| `--download-b03` | False | Télécharge B03 pour le masque NDWI |
| `--clear-previous` | False | Supprime les détections précédentes |
| `--n-clusters` | 4 | Nombre de clusters K-Means |

**Flux `handle()` :**

1. `APIHealthChecker().run_all_checks()` + `assert_minimum_viable()` → bloque si aucune source
2. `get_sentinel_images(date_t1, date_t2)` → charge 2 `ImageSatellite` depuis la BDD ✅ **CORRIGÉ** — le bloc `--download-b03` est maintenant exécuté **après** cette étape (évite `TypeError: strptime(None)`)
3. Si `--download-b03` → `download_b03_cdse(d1, d1+90j)` pour T1 et T2. Si CDSE échoue (HTTP 403) → fallback `synthesize_b03(B04, B08)` automatique ✅ **CORRIGÉ**
4. Validation de l'intervalle T1-T2 : avertissement si < 90 jours ou > 540 jours
5. Avertissement saisons différentes (anomalie B36)
6. Si `--clear-previous` : `DetectionConstruction.objects.all().delete()`
7. Selon le mode :
   - `--use-tinycd` → `calculate_tinycd_pipeline()` → `DeepLearningDetector.detect()`
   - `--use-ai` → `calculate_ai_pipeline()` (K-Means + NDBI réel)
   - Défaut → `calculate_ndbi_pipeline()` (NDBI/BSI/NDVI/BUI)
8. `extract_change_regions(changes_dict)` → régions WGS84 + NDBI médian
9. Si `--use-hf-ai` : `HuggingFaceAIClient().batch_validate(regions, ndbi_t1, ndbi_t2)`
10. `process_4couches_verification(regions, image_metadata)` → écriture BDD
11. `print_detection_statistics()` → résumé console

**Méthodes clés :**

*`calculate_ai_pipeline(img_t1, img_t2, calc)` :*
- Ouvre B04/B08/B11 des deux dates en mémoire
- Calcule NDBI/BSI réels (pour la vérification ultérieure)
- `AIDetector.predict_buildings()` → mask_t1 et mask_t2
- Applique masque SCL (classes 3,6,8,9,10) si disponible
- B03 synthétique si `--download-b03` → `calculate_ndwi_from_paths()` → masque eau NDWI
- `new_constructions = (mask_t2==1) & (mask_t1==0) & ~water_proxy`
- Retourne le dict de changements

*`extract_change_regions(changes, img_t1, img_t2, calc)` :*
- Pour chaque type de changement (new_construction, soil_activity, demolition) :
  - `NDBICalculator.extract_change_regions(masque, min_size)` → régions pixels
  - `_pixel_region_to_geojson(region, raster_transform)` → polygone bbox WGS84
  - Calcul médiane NDBI T1/T2/BSI sur la bbox de la région (**CORRECTIF #1** vs ancienne valeur centroïde unique)
  - `compute_confidence()` → score [0.0, 1.0]
- Retourne liste de dicts région enrichis

*`_pixel_region_to_geojson(region, transform)` :*
- Convertit les coordonnées pixel (row, col) en (longitude, latitude) via `rasterio.transform.xy()` (**CORRECTIF A6** : coordonnées WGS84 correctes)
- Construit un polygone GeoJSON bbox à partir des 4 coins de la région

*`process_4couches_verification(regions, image_metadata)` :*
- Crée `Verification4Couches()` et `DetectionPipeline()`
- Appelle `pipeline.process_detection_regions(regions, image_metadata)`
- Gère les erreurs par région sans interrompre le traitement des autres

*`print_detection_statistics()` :*
- Agrégations Django : `DetectionConstruction.objects.values('status').annotate(count=Count('id'))`
- Affiche le tableau de bord texte final dans la console

---

#### `commands/import_sentinel.py`

**Rôle :** Importe des images Sentinel-2 depuis des fichiers TIFF locaux en créant des enregistrements `ImageSatellite`. Supporte deux formats de nommage.

**Arguments CLI :**
- `--folder` : dossier source (défaut : `BASE_DIR/module1_urbanisme/data_use/sentinel_api_exports`)
- `--dry-run` : affiche sans créer en base

**Méthodes :**

*`_analyze_sentinel_files(folder_path)` :*
Détecte automatiquement le format :
- **Nouveau format** (`sentinel_api_exports/`) : sous-dossiers `YYYY-MM-DD/`, fichiers `BXX_YYYY-MM-DD.tif`. Détecte B04, B08, B11, SCL (fichier contenant "SCL").
- **Ancien format** (flat) : tous les TIFF dans le même dossier, nommés `2024-01-29-00-00_..._B08_(Raw).tiff`. Parsé via `_parse_sentinel_filename()`.

*`_parse_sentinel_filename(filename)` :*
- Parse le format `2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B08_(Raw).tiff`
- Extrait la date depuis la première partie (YYYY-MM-DD)

*`_create_image_record(date_str, files)` :*
- Vérifie la présence des bandes obligatoires B08 et B11 (B04 optionnel pour BSI)
- `ImageSatellite.objects.create(bands=bands, ...)` avec chemins absolus (**CORRECTIF A8** : `settings.BASE_DIR` au lieu de chemins relatifs)

---

#### `commands/import_sentinel_api.py`

**Rôle :** Télécharge automatiquement les images Sentinel-2 via les APIs (Phase 3) et les enregistre en base.

**Arguments CLI :**
- `--date` : date cible (obligatoire, format YYYY-MM-DD)
- `--source` : forcer une source spécifique (`sh`, `cdse`, `pc`)

**Flux `handle()` :**
1. `SentinelDataFetcher()` → initialise les 3 sources
2. Si `--source` spécifié : désactive les autres sources via `fetcher._cdse_available = False`, etc.
3. `fetcher.get_bands_for_date(target_date, bands=["B04","B08","B11","SCL"], date_window_days=45)`
4. Prépare `export_dir = BASE_DIR/module1_urbanisme/data_use/sentinel_api_exports/{target_date}/`
5. Pour chaque bande : `from_bounds(bbox, width, height)` → transform affine → sauvegarde TIFF géoréférencé
6. Profil TIFF : `float32` pour B04/B08/B11, `uint8` pour SCL. CRS : `'+proj=longlat +datum=WGS84 +no_defs'`. Compression LZW.
7. `ImageSatellite.objects.update_or_create(date_acquisition=acq_date, defaults={bands_paths, scl_path, processed=False})`

---

#### `commands/import_cadastre.py`

**Rôle :** Importe le cadastre V10 de Treichville depuis le fichier GeoJSON local.

**Arguments CLI :**
- `--file` : chemin vers le GeoJSON (défaut : `module1_urbanisme/data_use/cadastre_treichville_v10 (1).geojson`)
- `--dry-run` : affiche sans créer en base

**Flux `handle()` :**
1. Lecture JSON du fichier cadastre
2. Extraction des `features` GeoJSON et des `_metadata` (version, nb zones)
3. Pour chaque feature : `_parse_feature()` → `ZoneCadastrale.objects.create()` ou update si zone_id existant
4. `_print_statistics()` : agrégation `values('buildable_status').annotate(count=Count('id'))` (**CORRECTIF A9** : `Count` importé depuis `django.db.models`)

*`_parse_feature(feature)` :*
- Extrait `zone_id`, `name`, `zone_type` depuis `properties`
- Mapping `zone_status` → `buildable_status` : `"forbidden"` → `"forbidden"`, `"conditional"` → `"conditional"`, tout autre → `"buildable"`
- `GEOSGeometry(json.dumps(geometry))` → géométrie PostGIS

---

#### `commands/import_google_buildings.py`

**Rôle :** Importe les empreintes de bâtiments Google Open Buildings V3 (mai 2023) via Google Earth Engine ou un fichier GeoJSON local.

**Arguments CLI :**
- `--min-confidence` : seuil de confiance minimum (défaut : 0.65)
- `--bbox` : bounding box (défaut : Treichville `-4.03001,5.28501,-3.97301,5.32053`)
- `--clear` : supprime les empreintes existantes avant import
- `--dry-run` : statistiques sans import
- `--from-geojson` : fichier GeoJSON local (mode offline/test)

**Méthodes :**

*`_load_from_gee(bbox, min_confidence)` :*
- `ee.Initialize(project=GEE_PROJECT_ID)`
- Charge `ee.FeatureCollection("GOOGLE/Research/open-buildings/v3/polygons")` filtrée sur la bbox et la confiance
- Téléchargement par lots de 5000 features via `.toList(count).slice(offset, end)`
- Retourne liste de dicts `{geometry, confidence, area_in_meters, full_plus_code}`

*`_load_from_geojson(filepath, min_confidence)` :*
- Charge le fichier GeoJSON local
- Filtre par `confidence >= min_confidence`
- Retourne la même structure que `_load_from_gee()`

*`_import_features(features)` :*
- `GEOSGeometry(json.dumps(feat["geometry"]))` → geom PostGIS
- `MicrosoftFootprint(geometry=geos_geom, source="Google_V3_2023", date_reference="2023-05", confidence_score=...)`
- `bulk_create` par chunks de 500 dans `transaction.atomic()`

*`_print_stats(features)` :*
- Répartition par niveau de confiance : Rouge (0.65-0.70), Jaune (0.70-0.75), Vert (≥0.75)

---

#### `commands/import_microsoft.py`

**Rôle :** Importe les Microsoft Building Footprints depuis un fichier `.geojsonl` (JSON Lines — une feature par ligne).

**Arguments CLI :**
- `--file` : fichier source (défaut : `module1_urbanisme/data_use/Abidjan_33333010.geojsonl`)
- `--bbox` : bounding box Treichville
- `--limit` : limite de features (0 = illimitée)
- `--dry-run` : statistiques sans import

**Méthodes clés :**

*`_is_in_bbox(feature, bbox)` :*
**CORRECTIF A7 :** Teste si le polygone intersecte la bounding box en calculant l'enveloppe AABB du polygone entier (pas seulement le premier point). Algorithme :
```python
lons = [c[0] for c in all_coords]
lats = [c[1] for c in all_coords]
poly_min/max_lon/lat = min/max(lons/lats)
# Chevauchement AABB (même partiel)
return not (poly_max_lon < bbox.min_lon or poly_min_lon > bbox.max_lon or ...)
```

*`_parse_feature(feature)` :*
- `GEOSGeometry(json.dumps(geometry))` → géométrie PostGIS
- ✅ **CORRIGÉ (D17)** : `source = "Google_V3_2023"` — valeur valide, cohérente avec les `SOURCE_CHOICES` (`Google_V3_2023`, `Google_Temporal_V1`). `Microsoft_2020` retiré des choix.

**CORRECTIF B1 :** `bulk_create` par chunks de 500 (au lieu d'INSERT un par un).

---

### 📁 templates/module1/

---

#### `templates/module1/base.html`

**Rôle :** Template HTML de base (21 Ko). Tous les autres templates héritent de celui-ci via `{% extends "module1/base.html" %}`.

**Style :** "Cyber Tactique" — thème Dark Mode avec fond `#0a0e17` (noir bleuté), accents `#00d4ff` (cyan électrique), rouge `#ff4757`, vert `#2ed573`, orange `#ffa502`. Variables CSS `:root` pour la cohérence globale.

**Bibliothèques incluses :**
- Leaflet.js 1.9.4 (cartes interactives)
- Chart.js 4.4.0 (graphiques statistiques)
- Font Awesome 6.5.0 (icônes)
- Google Fonts Orbitron (titres)

**Structure :**
- Barre de navigation avec le logo CIV-EYE, les statistiques actives (alertes rouges, oranges en direct), liens de navigation
- Sidebar de navigation latérale
- `{% block content %}` → zone principale de chaque page
- Alertes flash Django messages
- Footer avec version et mentions

---

#### `templates/module1/dashboard.html`

**Rôle :** Tableau de bord principal (36 Ko). Page d'accueil sur `/`.

**Sections :**
1. **Cartes statistiques** (4 cartes) : Total zones cadastrales, Infractions rouges (infraction_zonage), Inspections requises (sous_condition), Conformes. Valeurs dynamiques depuis `context`.
2. **Graphique donut** Chart.js : répartition des alertes par niveau (rouge/orange/vert/veille). Données chargées via `api_statistics`.
3. **Carte Leaflet interactive** : tiles OpenStreetMap. Couche 1 : détections GeoJSON depuis `/api/detections-geojson/` — cercles colorés par status. Couche 2 : zones cadastrales depuis `/api/zones-geojson/` — polygones colorés par buildable_status. Popups sur clic avec infos et lien "Voir le détail".
4. **Tableau des 10 dernières détections** : date, status, alert_level (badge coloré), surface, confiance, lien vers le détail.

---

#### `templates/module1/detection_detail.html`

**Rôle :** Page de détail d'une détection (27 Ko). Accessible sur `/detections/<id>/`.

**Sections :**
1. **En-tête** : badge alert_level, date, status avec emoji.
2. **Carte Leaflet** centrée sur la géométrie de la détection. Marqueur rouge sur le centroïde.
3. **Graphique barre** Chart.js : comparaison NDBI T1 vs T2 (signal avant/après construction).
4. **Panneau technique** : ndbi_t1, ndbi_t2, bsi_value, surface_m2, confidence (barre de progression), present_in_microsoft, present_in_t1_sentinel.
5. **Contexte légal** : zone cadastrale (nom, type, buildable_status), surface de la zone.
6. **Bouton "Vérifier en HD sur Google Maps"** : lien vers Google Maps satellite à `lat,lon` avec zoom 20 — permet à l'agent de voir la réalité terrain en haute résolution.
7. **Iframe GEE** : visualisation split-screen T1/T2 via l'application Google Earth Engine déployée. URL = `https://ee-VotreCompteGEE.projects.earthengine.app/view/civ-eye-compare?lat={lat}&lon={lon}` — **placeholder à remplacer manuellement**.
8. **Formulaire feedback terrain** : sélection `statut_traitement`, `commentaire_terrain`. Soumission PATCH vers `api/v1/detections/{id}/traiter/`.

---

#### `templates/module1/detections_list.html`

**Rôle :** Liste paginée des détections (14 Ko). Accessible sur `/detections/`.

**Sections :**
- Filtres : select `status` et `alert_level` (soumis en GET)
- Tableau des détections : colonnes date, zone, status (badge emoji coloré), alert_level, NDBI T2, surface, confiance, lien détail
- Codes couleur par alert_level : rouge → `#ff4757`, orange → `#ffa502`, vert → `#2ed573`, veille → `#00d4ff`

---

#### `templates/module1/zones_cadastrales.html`

**Rôle :** Liste des zones cadastrales (5.3 Ko). Accessible sur `/zones/`.

**Sections :**
- Tableau : zone_id, name, zone_type, buildable_status (badge coloré), nombre de détections (annotate), lien vers détail

---

#### `templates/module1/zone_detail.html`

**Rôle :** Détail d'une zone cadastrale (4.6 Ko). Accessible sur `/zones/<zone_id>/`.

**Sections :**
- Informations de la zone : zone_id, name, type, statut légal
- Carte Leaflet avec la géométrie de la zone
- Liste des détections dans cette zone

---

#### `templates/module1/404.html`

**Rôle :** Page d'erreur 404 personnalisée. Cohérente avec le thème dark mode "Cyber Tactique".

---

### 📁 module2_agroecologie/ et module3_orpaillage/

---

**Rôle prévu :** Modules futurs du projet CIV-EYE pour l'agriculture (surveillance des cultures, déforestation, zones humides) et l'orpaillage illégal (détection des mines artisanales par anomalies spectrales dans les rivières).

**État actuel :** Squelettes Django entièrement vides.

| Fichier | Taille | Contenu |
|---|---|---|
| `models.py` | 60 octets | `from django.db import models` uniquement |
| `views.py` | 66 octets | `from django.shortcuts import render` uniquement |
| `admin.py` | 66 octets | `from django.contrib import admin` uniquement |
| `tests.py` | 66 octets | `from django.test import TestCase` uniquement |
| `apps.py` | 100 octets | `AppConfig` standard |
| `pipeline/` | — | Répertoire vide |
| `migrations/` | — | Migration initiale vide |

**Note :** `module2_agroecologie` et `module3_orpaillage` sont dans `INSTALLED_APPS` mais n'ont aucune URL enregistrée dans `config/urls.py`. Les templates `templates/module2/` et `templates/module3/` sont aussi des répertoires vides.

---

### 📁 tests/

---

#### `tests/test_pipeline_validation.py`

**Rôle :** Script de validation du pipeline (310 lignes). 7 tests exécutables directement via `python tests/test_pipeline_validation.py`. Vérifie l'environnement Python, la lecture des TIFF Sentinel, les calculs NDBI/BSI, et l'intégration Django.

**Tests :**

| Test | Description |
|---|---|
| TEST 1 | Imports Python : numpy, rasterio, shapely, scipy |
| TEST 2 | Lecture des 5 fichiers TIFF Sentinel (T1 B08/B11, T2 B04/B08/B11) |
| TEST 3 | Calcul NDBI T1 et T2 — vérifie plage [-1,1] et nombre de pixels bâtis |
| TEST 4 | Calcul BSI (✅ D9 : formule complète `((B11+B04)-(B08+B02))/...` + fallback `(B11-B08)/(B11+B08)`) — vérifie la logique BSI_approx |
| TEST 5 | Détection changements T1→T2 — compte nouvelles constructions, sol, total |
| TEST 6 | Spatialité Shapely (Correctif A2) — containment et intersection polygon-polygon |
| TEST 7 | Django setup + modèles — compte les enregistrements et vérifie alert_level valides |

✅ **CORRIGÉ (D18)** : Chemins TIFF mis à jour — `SENTINEL_DIR` → `sentinel_api_exports`, dates → `2024-02-15` / `2025-01-15`, toutes les bandes T1+T2 (B04, B08, B11, SCL) référencées avec le format `B08_{date}.tif`. Tests 2-5 opérationnels.

---

#### `tests/integration/test_audit.py`

**Rôle :** Test d'intégration complet (750 lignes). Vérifie tout le pipeline avec la vraie base de données.

**Sections :**
- ÉTAPE 0 : config Django, connexion BDD, version PostGIS, comptage modèles
- ÉTAPE 1 : import cadastre (parse features GeoJSON, GEOSGeometry)
- ÉTAPE 2 : import footprints (filtre BBOX, bulk_create)
- ÉTAPE 3 : calcul NDBI (valeurs réalistes, rééchantillonnage)
- ÉTAPE 4 : détection changements (masques, régions connexes)
- ÉTAPE 5 : vérification 4 couches (requêtes PostGIS ST_DWithin, ST_Contains)
- ÉTAPE 6 : pipeline complet (création DetectionConstruction en base)
- ÉTAPE 7 : endpoints API (statistiques, GeoJSON)

---

#### `tests/integration/test_gee.py` et `tests/integration/test_sh.py`

**Rôle :** Tests d'intégration des APIs externes. `test_gee.py` teste l'initialisation GEE et le téléchargement d'une image Sentinel-2. `test_sh.py` teste l'authentification OAuth2 Sentinel Hub et la récupération d'une image via evalscript.

---

#### `tests/test_db.py`, `tests/test_lints.py`

**Rôle :** `test_db.py` vérifie les migrations Django et les contraintes de base de données. `test_lints.py` vérifie la syntaxe Python de tous les fichiers du projet via `py_compile`.

---

### 📁 test_special/

---

**Rôle :** Suite de tests spéciaux créés pendant le hackathon pour diagnostiquer des problèmes spécifiques. 11 fichiers organisés par thème.

| Fichier | Ce qu'il teste |
|---|---|
| `run_all_tests.py` | Orchestre tous les tests spéciaux en séquence |
| `test_API.py` | Endpoints API REST (`/api/v1/detections/`, `/api/statistics/`) |
| `test_CIV.py` | Contexte ivoirien : seuils NDBI, matériaux locaux, calibration |
| `test_CMD.py` | Commandes management (import_cadastre, import_sentinel, run_detection) |
| `test_DB.py` | Base de données : migrations, contraintes, requêtes spatiales |
| `test_DB_REAL.py` | Tests BDD avec données réelles (nécessite PostGIS actif) |
| `test_ENV.py` | Variables d'environnement : présence des clés API, formats |
| `test_PIPE.py` | Pipeline NDBI/K-Means avec données mockées |
| `test_PIPE_REAL.py` | Pipeline avec vrais fichiers TIFF Sentinel-2 |
| `test_ROB.py` | Robustesse : images corrompues, bandes manquantes, valeurs nulles |
| `test_WEB.py` | Interface web : dashboard, templates, endpoints JSON |

---

### 📁 scripts/

---

#### `scripts/auto_fix_and_verify.py`

**Rôle :** Script d'analyse, correction et vérification automatique du Module 1 (226 lignes). Exécutable directement via `python scripts/auto_fix_and_verify.py`.

**Classe `AutoFixVerify` :**
- `check_django_system()` : `python manage.py check`
- `check_database()` : compte les enregistrements de chaque modèle via shell
- `check_templates()` : vérifie la présence des 5 templates critiques
- `check_server_status()` : teste 4 URLs HTTP sur port 8001
- `test_api_endpoints()` : teste tous les endpoints `/api/statistics/`, `/api/detections-geojson/`, `/api/zones-geojson/`, `/`, `/detections/`
- `generate_report()` : rapport final avec comptage corrections/erreurs

---

#### `scripts/diagnose_500_errors.py`

**Rôle :** Script de diagnostic ciblé sur les erreurs HTTP 500 (118 lignes).

**Vérifications :**
1. Test via `django.test.Client` pour capturer la trace Python
2. Requête HTTP directe avec capture du contenu de l'erreur
3. Résolution d'URL via `get_resolver().resolve('/')`
4. Import direct de `views_web.dashboard` pour détecter les erreurs d'import
5. Vérification du template `dashboard.html` (taille, syntaxe Django)

---

#### `scripts/export_detections_gps.py`

**Rôle :** Exporte les détections en CSV GPS pour les agents terrain ou l'import SIG. Génère `exports/export_detections_gps.csv` (12 Ko).

**Colonnes CSV :** id, date_detection, latitude, longitude, status, alert_level, ndbi_t1, ndbi_t2, bsi_value, surface_m2, confidence, zone_cadastrale, zone_type, buildable_status.

---

#### `scripts/audits/audit_module1_full.py` et `audit_module1_p0p1.py`

**Rôle :** Scripts d'audit complets (exécutés pendant le hackathon). Vérifient l'application de tous les correctifs (A1-A10, L1-L6, B1, M12) en testant les fonctions correspondantes.

---

### 📁 NVideDocx/ (documentation interne)

---

#### `NVideDocx/analyse_ia_et_earth.md`

**Rôle :** Analyse technique détaillée (1094 lignes). Document de référence ayant guidé les décisions d'architecture du pipeline.

**Contenu principal :**

*PARTIE 1 — 16 cas terrain non couverts :*

| # | Cas terrain | Détecté ? | Raison |
|---|---|---|---|
| 1 | Nouvelle construction simple (dalle→murs→toit tôle) | ✅ | — |
| 2 | Bâtiment rasé/démoli | ✅ (après L1) | NDBI baisse → delta négatif |
| 3 | Extension en hauteur (ajout d'un étage) | ❌ Impossible | Surface au sol inchangée à 10m/px |
| 4 | Surélévation partielle (véranda, auvent) | ❌ Impossible | Trop petit pour 10m/px |
| 5 | Construction sous arbre/canopée | ❌ Manqué | NDVI domine le signal NDBI |
| 6 | Dalle en béton nue (sans construction) | ⚠️→✅ Amélioré (D9) | BSI complet ((B11+B04)-(B08+B02)) meilleure discrimination sol nu |
| 7 | Route ou parking asphalté | ⚠️ Faux positif | NDBI similaire au bâti — pas de donnée OSM routière |
| 8 | Tôle/bâche temporaire (marché, abri) | ⚠️ Faux positif | Signal fugace selon saison — vérification terrain requise |
| 9 | Mur de clôture/enceinte | ❌ Impossible | Trop étroit pour 10m/px — physique indépassable |
| 10 | Panneau solaire sur toit existant | ⚠️ Faux positif | Modifie réflectance SWIR — hors scope |
| 11 | Sol retourné (agriculture urbaine) | ⚠️→⚠️ Partiel (D9) | BSI complet améliore légèrement la discrimination |
| 12 | Nuages résiduels/ombre de nuage | ⚠️→✅ Partiel (L6) | Masque SCL (classes 3,6,8,9,10) implémenté — 35.3% pixels masqués |
| 13 | Construction en zone d'eau (remblais lagune) | ⚠️ Partiel | Proxy eau NDBI < -0.15 actif ; B03 absent par défaut (--download-b03) |
| 14 | Réhabilitation totale (rénovation illégale) | ❌ Non pris en compte | Bâtiment existant → filtré par Couche 1 — limitation logique |
| 15 | Construction souterraine | ❌ Impossible | Physiquement invisible en optique |
| 16 | Changement de matériaux (paille→tôle) | ⚠️ Faux positif | NDBI monte, structure inchangée — vérification terrain requise |

*PARTIE 2 — Améliorations L1-L6 planifiées :*
- L1 : Démolitions (delta NDBI négatif) → ✅ Implémenté
- L2 : Masque eau NDWI (B03) → ⚠️ Partiel (B03 absent par défaut)
- L3 : Masque végétation NDVI > 0.4 → ✅ Implémenté
- L4 : Filtre taille min=2/max=500 pixels → ✅ Implémenté
- L5 : Score confiance dynamique → ✅ Implémenté
- L6 : Masque nuages SCL → ✅ Implémenté

---

#### `NVideDocx/plan_complet_hackathon.md`

**Rôle :** Récapitulatif de l'avancement par phase (188 lignes). Identifie les actions manuelles restantes.

**État des phases :**

| Phase | Description | Statut |
|---|---|---|
| 0 | Corrections bloquantes (A1-A10) | ✅ Terminé en code |
| 1 | Améliorations logiques (L1-L6) | ✅ Terminé (L2 partiel) |
| 2 | Indices spectraux multi-couches (NDBI/BSI/NDVI/BUI) | ✅ Terminé |
| 3 | Acquisition automatique (SentinelDataFetcher) | ✅ Terminé en code |
| 4 | Compositing GEE multi-temporel | ✅ Script prêt, déploiement manuel requis |
| 5 | IA Machine Learning (K-Means) | ✅ En production |
| 6 | Interface web cartographique (Leaflet) | ✅ Terminé |
| 7 | SAR Sentinel-1 (anti-nuage) | ⚠️ Structuré, token entreprise requis |
| 8 | Deep Learning TinyCD (expérimental) | ⚠️ Poids à télécharger |

**Actions manuelles identifiées :** Télécharger B03 (NDWI), créer compte GEE, déployer gee_split_app.js, mettre à jour les clés API dans .env.

---

## ⚙️ SECTION 3 — FLUX D'EXÉCUTION COMPLET (PAS À PAS)

---

### ÉTAPE 0 — Initialisation de l'environnement Django

**Fichier :** `config/settings.py` (chargé automatiquement par Django au démarrage)

**Ce qui se passe :**
1. `environ.Env.read_env()` lit le fichier `.env` et charge toutes les variables dans l'espace d'environnement Python (`os.environ`)
2. La correction PROJ est appliquée : `os.environ['PROJ_LIB'] = rasterio.env.default_proj_lib()` force la base de données PROJ intégrée à rasterio, évitant le conflit avec celle de PostgreSQL
3. Les avertissements `pkg_resources` de rasterio sont supprimés
4. Si `DATABASE_URL=postgis://...` → Django configure le driver PostGIS et ajoute les DLL Windows au PATH
5. Si `DATABASE_URL` absent → Django utilise SQLite (`db.sqlite3`)

**En cas d'erreur :** Si `.env` est absent, les valeurs par défaut s'appliquent (SQLite, SECRET_KEY insécurisée). Le démarrage réussit mais le mode production serait dangereux.

---

### ÉTAPE 1 — Import du cadastre (exécuté une seule fois)

**Commande :** `python manage.py import_cadastre`
**Fichier principal :** `management/commands/import_cadastre.py`

**Ce qui se passe :**
1. `open("module1_urbanisme/data_use/cadastre_treichville_v10 (1).geojson")` → charge les 200+ zones cadastrales
2. Affichage des métadonnées : `version=10`, `zones=N déclarées`
3. Pour chaque feature GeoJSON :
   - `_parse_feature(feature)` : extrait `zone_id`, `name`, `zone_type`, mapping `zone_status → buildable_status`
   - `GEOSGeometry(json.dumps(geometry))` : convertit le polygone GeoJSON en objet PostGIS WGS84
   - `ZoneCadastrale.objects.filter(zone_id=...).exists()` : vérifie si la zone existe déjà
   - Si non : `ZoneCadastrale.objects.create(**zone_data)` (CORRECTIF A9 : Count importé correctement)
   - Si oui : `_update_zone(zone, zone_data)` (mise à jour des champs)
4. Résumé final : zones importées, zones ignorées (erreurs), statistiques par buildable_status

**Sortie attendue :** N enregistrements `ZoneCadastrale` avec géométries PostGIS.

---

### ÉTAPE 2 — Import des empreintes de bâtiments (exécuté une seule fois)

**Commande :** `python manage.py import_google_buildings --from-geojson <fichier>` (mode offline) ou sans `--from-geojson` si GEE configuré

**Fichier principal :** `management/commands/import_google_buildings.py`

**Ce qui se passe :**
1. Mode offline : `_load_from_geojson(filepath, min_confidence=0.65)` → lit le GeoJSON local, filtre par `confidence >= 0.65`
2. Mode GEE : `_load_from_gee(bbox, min_confidence)` → `ee.Initialize(project=GEE_PROJECT_ID)` → charge `GOOGLE/Research/open-buildings/v3/polygons` filtrée sur la bbox Treichville → téléchargement par lots de 5000
3. Si `--clear` : `MicrosoftFootprint.objects.all().delete()`
4. `_import_features(features)` : pour chaque feature :
   - `GEOSGeometry(json.dumps(feat["geometry"]))` → géom PostGIS
   - `MicrosoftFootprint(geometry=..., source="Google_V3_2023", date_reference="2023-05", confidence_score=...)`
   - Accumulation dans un buffer `chunk`
   - À 500 : `MicrosoftFootprint.objects.bulk_create(chunk)` dans `transaction.atomic()`
5. Résumé : N bâtiments importés avec répartition Rouge/Jaune/Vert

**Sortie attendue :** Des milliers d'enregistrements `MicrosoftFootprint` avec empreintes PostGIS.

---

### ÉTAPE 3 — Import des images Sentinel-2

**Option A (TIFF locaux) :** `python manage.py import_sentinel`
**Option B (téléchargement API) :** `python manage.py import_sentinel_api --date 2024-01-29`

**Fichiers :** `import_sentinel.py`, `import_sentinel_api.py`, `pipeline/sentinel_data_fetcher.py`

**Ce qui se passe (Option B — téléchargement API) :**
1. `SentinelDataFetcher()` → détecte les sources disponibles (Sentinel Hub, CDSE, Planetary Computer)
2. Si `--source sh/cdse/pc` : désactive les autres sources via `fetcher._cdse_available = False`, etc.
3. `fetcher.get_bands_for_date(target_date, bands=["B04","B08","B11","SCL"], date_window_days=45)` :
   - Essaie Sentinel Hub → si échec, CDSE → si échec, Planetary Computer
   - Retourne `{"B04": ndarray, "B08": ndarray, "B11": ndarray, "SCL": ndarray}` en float32 normalisé [0,1]
4. Création du dossier `sentinel_api_exports/{target_date}/`
5. Pour chaque bande :
   - `from_bounds(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, width, height)` → transform affine
   - Profil TIFF : `float32` (B04/B08/B11) ou `uint8` (SCL), CRS `+proj=longlat +datum=WGS84`, compression LZW
   - `rasterio.open(output_path, 'w', **profile).write(arr, 1)` → sauvegarde TIFF géoréférencé
6. `ImageSatellite.objects.update_or_create(date_acquisition=acq_date, defaults={bands: bands_paths, classification_map: scl_path, processed: False})`

**À répéter pour T2 (2025-01-13).**

**Sortie attendue :** 2 enregistrements `ImageSatellite` en base avec chemins absolus vers les TIFF dans `sentinel_api_exports/`.

---

### ÉTAPE 4 — Lancement du pipeline de détection

**Commande :** `python manage.py run_detection --date-t1 2024-01-29 --date-t2 2025-01-13 --use-ai`
**Fichier principal :** `management/commands/run_detection.py`

---

#### Sous-étape 4.1 — Diagnostic des APIs

`APIHealthChecker().run_all_checks()` :
- Teste les TIFF locaux dans `sentinel_api_exports/`
- Teste Sentinel Hub (OAuth2 réel)
- Teste CDSE (HTTP public)
- Teste Planetary Computer (clé API)
- Teste GEE (initialisation)
- Teste HuggingFace (token)
- Affiche le rapport avec indicateurs ✅/⚠️/❌

`assert_minimum_viable()` : si aucune source accessible → `RuntimeError` → arrêt.

---

#### Sous-étape 4.2 — Chargement des images T1 et T2

`get_sentinel_images(date_t1, date_t2)` :
- `ImageSatellite.objects.get(date_acquisition=date_t1)` → objet T1 (avec chemins TIFF)
- `ImageSatellite.objects.get(date_acquisition=date_t2)` → objet T2
- Vérification `ValueError` si moins de 2 images disponibles
- Validation intervalle : log avertissement si T2-T1 < 90 jours (pas assez de temps pour une construction) ou > 540 jours (trop long, risque de multiples constructions)
- Vérification saisons (B36) : avertissement si T1 et T2 sont dans des saisons pluvieuses différentes

---

#### Sous-étape 4.3a — Calcul spectral (mode --use-ai : K-Means)

`calculate_ai_pipeline(img_t1, img_t2, calc)` :
1. Ouvre B04/B08/B11 T1 via `rasterio.open(img_t1.bands["B04"])` → arrays numpy float32
2. Ouvre B04/B08/B11 T2 de même
3. Calcule NDBI T1, NDBI T2, BSI T2 via `NDBICalculator` (pour la validation ultérieure des seuils)
4. `AIDetector().predict_buildings(b04_t1, b08_t1, b11_t1)` → `mask_t1` (uint8, 1=bâti, 0=non-bâti)
5. `AIDetector().predict_buildings(b04_t2, b08_t2, b11_t2)` → `mask_t2`
6. Si SCL disponible : `NDBICalculator.apply_scl_mask(mask_t1, scl_t1_path, [3,6,8,9,10])` → masque pixels nuageux/eau sur mask_t1 et mask_t2
7. Si `--download-b03` : télécharge B03 → `calculate_ndwi_from_paths(b03, b08_t2)` → `water_mask` (pixels NDWI > 0)
8. Si B03 absent : proxy eau = `(ndbi_t2 < -0.15)`
9. `new_constructions = (mask_t2 == 1) & (mask_t1 == 0) & ~water_mask`
10. `demolished = (mask_t1 == 1) & (mask_t2 == 0) & ~water_mask`
11. `soil_activity` via BSI T2 > threshold_soil
12. Retourne `{'new_constructions': mask, 'soil_activity': mask, 'demolished': mask, 'all_changes': mask}`

---

#### Sous-étape 4.3b — Calcul spectral (mode NDBI empirique, par défaut)

`calculate_ndbi_pipeline(img_t1, img_t2, calc)` :
1. `calc.calculate_ndbi(b08_t1, b11_t1)` → `ndbi_t1` ndarray float64 [-1,1]
2. `calc.calculate_ndbi(b08_t2, b11_t2)` → `ndbi_t2`
3. `calc.calculate_bsi(b04_t2, b08_t2, b11_t2)` → `bsi_t2`
4. `calc.calculate_ndvi(b04_t2, b08_t2)` → `ndvi_t2`
5. `calc.calculate_bui(ndbi_t2, ndvi_t2)` → `bui_t2`
6. Si SCL T1 et T2 disponibles : `apply_scl_mask()` sur les 4 arrays
7. `calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2, ndvi_t2)` :
   - `new_constructions = (ndbi_t1 <= 0.2) & (ndbi_t2 > 0.2)` (NDBI monte au-dessus du seuil)
   - `demolished = (ndbi_t1 > 0.25) & (ndbi_t2 < 0.05)` (NDBI baisse fortement)
   - `soil_activity = (bsi_t2 > 0.15) & ~new_constructions`
   - Masque végétation : si `ndvi_t2 > 0.4` → exclusion
   - Masque eau proxy : `ndbi_t2 < -0.15` → exclusion

---

#### Sous-étape 4.4 — Extraction des régions de changement

`extract_change_regions(changes_dict, img_t1, img_t2, calc)` :
1. Pour chaque type (`new_constructions`, `soil_activity`, `demolished`) :
   - `calc.extract_change_regions(masque, min_size=min_region_size, max_size=500)` → liste de composantes connexes (label, size_px, bbox, centroïde pixel)
   - Pour chaque composante :
     - `surface_m2 = size_px × (10m × 10m)` = approximation à la résolution Sentinel-2
     - `_pixel_region_to_geojson(region, raster_transform)` : convertit bbox pixel → polygone WGS84 via `rasterio.transform.xy()` (**CORRECTIF A6**)
     - Extrait un crop de la bbox sur `ndbi_t1`, `ndbi_t2`, `bsi_t2` → calcule médiane (**CORRECTIF #1** vs ancienne valeur centroïde ponctuelle)
     - `calc.compute_confidence(ndbi_t1_med, ndbi_t2_med, bsi_med, size_px, cloud_pct)` → score [0,1]
     - Stocke `{'geojson': polygon, 'change_type': ..., 'ndbi_t1': float, 'ndbi_t2': float, 'bsi': float, 'surface_m2': float, 'confidence': float, 'centroid': (row, col)}`
2. Retourne liste totale des régions enrichies

---

#### Sous-étape 4.5 — Scoring IA local (optionnel, mode --use-hf-ai)

`HuggingFaceAIClient().batch_validate(regions, ndbi_t1, ndbi_t2)` :
1. Pour chaque région : extrait un crop 10×10 pixels autour du centroïde dans les arrays NDBI
2. `_local_ai_score(ndbi_t1_crop, ndbi_t2_crop, bsi_crop)` → score spectral pondéré [0.1, 0.95]
3. Met à jour `region['confidence'] = region['confidence'] × 0.7 + ai_score × 0.3`

---

#### Sous-étape 4.6 — Vérification 4 couches et écriture en base

`process_4couches_verification(regions, image_metadata)` :

Pour chaque région dans la liste :

**CAS 0 — Filtre surface :**
Si `region['surface_m2'] < 200` → `continue` (région rejetée, non écrite)

**Couche 1 — Google Open Buildings :**
`Verification4Couches._check_google_buildings(region['geojson'])` :
- `centroid_geos = GEOSGeometry(json.dumps(centroid_geojson))`
- `radius_degrees = 15 / 111320.0` (15m en degrés)
- `MicrosoftFootprint.objects.filter(geometry__dwithin=(centroid_geos, radius_degrees)).order_by('-confidence_score')` (requête PostGIS ST_DWithin)
- Selon le résultat et le score de confiance → 7 cas logiques (voir Section 2)
- Si `FAUX_POSITIF_PRE_EXISTANT` : `continue` (région rejetée)

**Couche 2 — Vérification NDBI T1 :**
Si `ndbi_t1 > 0.3` (1.5 × threshold_built) → `continue` (bâtiment pré-existant probable)

**Couche 3 — Cohérence spectrale CIV :**
`_is_valid_change(ndbi_t1, ndbi_t2, change_type, confidence_ia)` :
- Seuil ivoirien `CIV_NDBI_THRESHOLD = 0.10`
- Si `ndbi_t2 < CIV_NDBI_THRESHOLD` pour `new_construction` → `continue`

**Couche 4 — Classification cadastrale :**
`_classify_by_zoning(geometry_geojson, change_type, bsi_val, present_microsoft)` :
- PostGIS ST_Contains(centroïde, zone) ou ST_Intersects(polygone, zone)
- Retourne un dict `{status, alert_level, zone_cadastrale, message, verification_required, present_microsoft}`

**Création de l'enregistrement :**
`DetectionPipeline._create_detection_record(region, classification, ndbi_values)` :
- `GEOSGeometry(json.dumps(region['geojson']))` → géom PostGIS
- `DetectionConstruction.objects.create(date_detection=now(), zone_cadastrale=zone, geometry_geojson=geojson_str, ndbi_t1=..., ndbi_t2=..., bsi_value=..., surface_m2=..., confidence=..., present_in_microsoft=..., present_in_t1_sentinel=..., status=..., alert_level=..., verification_required=...)`
- Tout dans `transaction.atomic()`

---

#### Sous-étape 4.7 — Affichage des statistiques finales

`print_detection_statistics()` :
- `DetectionConstruction.objects.values('status').annotate(count=Count('id'))` → comptage par statut
- `DetectionConstruction.objects.values('alert_level').annotate(count=Count('id'))` → comptage par niveau
- Affichage en tableau ASCII dans la console

---

### ÉTAPE 5 — Consultation des résultats

**Commande :** `python manage.py runserver` → navigateur → `http://127.0.0.1:8000/`

**Flux dashboard :**
1. `GET /` → `views_web.dashboard(request)`
2. Agrégations BDD : `DetectionConstruction.objects.aggregate(Count...)` + `ZoneCadastrale.objects.aggregate(...)`
3. `DetectionConstruction.objects.order_by('-date_detection')[:10]` → 10 dernières détections
4. `render(request, 'module1/dashboard.html', context)` → template rendu côté serveur

**Flux carte Leaflet (requête Ajax) :**
1. `dashboard.html` charge et exécute le JavaScript Leaflet
2. `fetch('/api/detections-geojson/')` → `views_web.api_detections_geojson(request)` → itère toutes les `DetectionConstruction` → construit `FeatureCollection` GeoJSON → `JsonResponse`
3. `fetch('/api/zones-geojson/')` → `views_web.api_zones_geojson(request)` → construit `FeatureCollection` zones → `JsonResponse`
4. Leaflet affiche les cercles colorés et polygones sur la carte OpenStreetMap

**Flux API REST (consommation externe) :**
1. `GET /api/v1/detections/` → `DetectionConstructionViewSet.list()` → queryset paginé → `DetectionConstructionSerializer(many=True).data` → JSON
2. `GET /api/v1/detections/?status=infraction_zonage&alert_level=rouge` → filtre Django-filter → JSON filtré
3. `GET /api/v1/detections/statistics/` → action `statistics()` → JSON agrégé

---

## 🔗 SECTION 4 — CARTOGRAPHIE DES FLUX DE DONNÉES

---

### 4.1 — Points de départ des données (sources primaires)

| Source | Format | Fichier récepteur | Obligatoire |
|---|---|---|---|
| Fichiers TIFF Sentinel-2 locaux | GeoTIFF float32 | `import_sentinel.py` | Non (si API disponible) |
| API Sentinel Hub | OAuth2 + evalscript | `sentinel_data_fetcher.py` | Non (si CDSE ok) |
| API CDSE Copernicus | STAC public + COG | `sentinel_data_fetcher.py` | Recommandé (gratuit) |
| API Planetary Computer | STAC + clé API | `sentinel_data_fetcher.py` | Non |
| GeoJSON cadastre local | GeoJSON (polygones) | `import_cadastre.py` | Oui |
| GEE Google Open Buildings | GEE API + FeatureCollection | `import_google_buildings.py` | Recommandé |
| GeoJSON Open Buildings local | GeoJSON offline | `import_google_buildings.py` | Alternative GEE |
| Fichier `.geojsonl` Microsoft | GeoJSON Lines | `import_microsoft.py` | Optionnel |

---

### 4.2 — Transformations successives des données

```
TIFF physiques (B04/B08/B11/SCL sur disque)
        ↓  rasterio.open() → read(1).astype(float32)
arrays numpy float32 [0,1] normalisés
        ↓  NDBICalculator ou AIDetector
indices spectraux ndarray float64 [-1,1] : NDBI, BSI, NDVI, BUI
        ↓  detect_changes() avec masques SCL/NDWI/NDVI
masques booléens de changement (new_constructions, demolished, soil_activity)
        ↓  scipy.ndimage.label() ou cv2.connectedComponentsWithStats()
composantes connexes (label, size_px, bbox, centroïde pixel)
        ↓  rasterio.transform.xy() [CORRECTIF A6]
coordonnées géographiques WGS84 (longitude, latitude)
        ↓  _pixel_region_to_geojson()
polygones GeoJSON WGS84 (bbox rectangulaire)
        ↓  médiane NDBI sur bbox [CORRECTIF #1] + compute_confidence()
régions enrichies : {geojson, change_type, ndbi_t1, ndbi_t2, bsi, surface_m2, confidence}
        ↓  HuggingFaceAIClient.batch_validate() [optionnel]
régions avec confidence ajustée (70/30 spectral/IA)
        ↓  Verification4Couches.verify_detection()
classification : {status, alert_level, zone_cadastrale, verification_required}
        ↓  DetectionPipeline._create_detection_record()
DetectionConstruction (PostgreSQL/PostGIS)
        ↓  DetectionConstructionSerializer ou views_web.api_detections_geojson()
JSON REST / FeatureCollection GeoJSON
        ↓  Django templates (Leaflet.js, Chart.js)
Interface HTML interactive
```

---

### 4.3 — Schéma des dépendances entre fichiers

```
manage.py
    └─→ config/settings.py (.env, INSTALLED_APPS, DB)
    └─→ config/urls.py
            ├─→ module1_urbanisme/urls_web.py
            │       └─→ views_web.py → models.py (4 modèles)
            ├─→ module1_urbanisme/urls.py
            │       └─→ views.py → serializers.py → models.py
            └─→ module1_urbanisme/urls_simple.py
                    └─→ views_simple.py → serializers_simple.py → models.py

management/commands/run_detection.py
    ├─→ pipeline/api_health_checker.py
    │       ├─→ models.ImageSatellite (comptage)
    │       └─→ [sentinelhub, earthengine, urllib.request, requests]
    ├─→ models.ImageSatellite (chargement T1/T2)
    ├─→ pipeline/ndbi_calculator.py
    │       └─→ [rasterio, numpy, scipy.ndimage]
    ├─→ pipeline/ai_detector.py
    │       └─→ [numpy, cv2, sklearn.cluster]
    ├─→ pipeline/deep_learning_detector.py [optionnel --use-tinycd]
    │       └─→ [torch, torchvision, tinycd_models/]
    ├─→ pipeline/b03_synthesizer.py [si --download-b03]
    │       └─→ [rasterio, numpy]
    ├─→ pipeline/b03_downloader.py [si --download-b03]
    │       └─→ [pystac_client, rasterio]
    ├─→ pipeline/huggingface_ai_client.py [si --use-hf-ai]
    ├─→ pipeline/sentinel1_sar.py [si --use-sar, stub]
    └─→ pipeline/verification_4_couches.py
            ├─→ models.ZoneCadastrale (ST_Contains, ST_Intersects)
            ├─→ models.MicrosoftFootprint (ST_DWithin)
            └─→ models.DetectionConstruction (create)

management/commands/import_sentinel_api.py
    └─→ pipeline/sentinel_data_fetcher.py
            ├─→ [sentinelhub] (Sentinel Hub API)
            ├─→ [pystac_client] (CDSE STAC)
            └─→ [planetary_computer, pystac_client] (Planetary Computer)

management/commands/import_cadastre.py
    └─→ data_use/cadastre_treichville_v10 (1).geojson
    └─→ models.ZoneCadastrale

management/commands/import_google_buildings.py
    ├─→ [earthengine-api] (GEE)
    └─→ models.MicrosoftFootprint

management/commands/import_microsoft.py
    └─→ data_use/Abidjan_33333010.geojsonl (gitignored)
    └─→ models.MicrosoftFootprint
```

---

### 4.4 — Dépendances externes critiques

| Bibliothèque | Version | Rôle | Mode sans clé |
|---|---|---|---|
| Django | 5.0.3 | Framework web, ORM, admin | Non applicable |
| rasterio | 1.3.9 | Lecture/écriture TIFF géospatiaux, rééchantillonnage | Fichiers locaux |
| numpy | ≥1.26.4 | Calcul matriciel sur les images | Toujours disponible |
| scikit-learn | ≥1.3.0 | MiniBatchKMeans dans AIDetector | Toujours disponible |
| opencv-python-headless | ≥4.9.0 | Sobel, morphologie, composantes connexes | Toujours disponible |
| scipy | ≥1.12.0 | `ndimage.label` pour les régions | Toujours disponible |
| django.contrib.gis | intégré | ST_Contains, ST_DWithin, GEOSGeometry | PostGIS requis |
| pystac-client | 0.8.5 | Catalogue CDSE Copernicus (source gratuite) | Toujours disponible |
| sentinelhub | 3.11.5 | API Sentinel Hub (source premium) | Clé requise |
| earthengine-api | latest | Google Open Buildings V3, composites GEE | Compte GEE requis |
| torch | ≥2.0.0 | TinyCD deep learning | Poids à télécharger |
| planetary-computer | 1.0.0 | Microsoft Planetary Computer | Clé optionnelle |
| psycopg2-binary | non fixée | Driver PostgreSQL/PostGIS | PostGIS requis |

---

### 4.5 — Formats de données à chaque étape

| Étape | Format d'entrée | Format de sortie |
|---|---|---|
| Import Sentinel | Néant / URL API | TIFF GeoTIFF WGS84, float32, LZW |
| Lecture TIFF | TIFF (disk) | ndarray numpy (H×W) float32 |
| Calcul NDBI | ndarray B08, B11 | ndarray float64 [-1,1] |
| Calcul NDVI | ndarray B04, B08 | ndarray float64 [-1,1] |
| Détection changements | ndarrays NDBI T1/T2, BSI | Dict[str, ndarray bool] |
| Extraction régions | ndarray bool | List[Dict{bbox, centroid, size}] |
| Géoréférencement | bbox pixels + transform | Polygone GeoJSON WGS84 |
| Vérification 4 couches | GeoJSON, NDBI, BSI | Dict{status, alert_level, zone} |
| Écriture BDD | Dict classification | `DetectionConstruction` (PostGIS) |
| API REST | QuerySet Django | JSON paginé (DRF) |
| Carte Leaflet | URL endpoint | GeoJSON FeatureCollection |

---

## 🐛 SECTION 5 — AUDIT TECHNIQUE : BUGS, PROBLÈMES ET FRAGILITÉS

---

> **Légende des niveaux :** 🔴 CRITIQUE/ÉLEVÉ — impact direct sur le fonctionnement | 🟠 MOYEN — comportement incorrect mais pas de crash | 🟡 FAIBLE — dette technique ou portabilité

---

### 🔴 PROBLÈME 1 — BUG CONFIRMÉ : NameError dans sentinel1_sar.py

**Localisation :** `module1_urbanisme/pipeline/sentinel1_sar.py`, fonction `evaluate_sar_backscatter_delta()`, ligne 24

**Catégorie :** Bug confirmé à l'exécution

✅ **CORRIGÉ (D19)** : `delta_vv = vv_t2 - vv_t1` est présent à la ligne 24 du fichier. La fonction est correcte. L'impact est nul dans le flux actuel (appelé uniquement via `fetch_and_evaluate_sar_for_bbox()` qui retourne un stub statique jusqu'à obtention du token Sentinel Hub entreprise).

---

### 🔴 PROBLÈME 2 — SOURCE INVALIDE dans import_microsoft.py

**Localisation :** `module1_urbanisme/management/commands/import_microsoft.py`, méthode `_parse_feature()`, ligne ~181

**Catégorie :** Donnée incorrecte en base

✅ **CORRIGÉ (D17)** : `source = "Google_V3_2023"` (valeur valide, données Google Open Buildings). `Microsoft_2020` supprimé des `SOURCE_CHOICES` du modèle. SOURCE_CHOICES actuel :
- `'Google_V3_2023'` — Google Open Buildings V3 (Mai 2023)
- `'Google_Temporal_V1'` — Google Open Buildings Temporal V1

```python
def _parse_feature(self, feature: dict) -> dict:
    geometry = feature.get("geometry")
    return {
        "geometry": GEOSGeometry(json.dumps(geometry)),
        "source": "Google_V3_2023",  # ← CORRIGÉ
        "source_file": "Abidjan_33333010.geojsonl",
        "date_reference": "~2023-2024",
    }
```

---

### 🔴 PROBLÈME 3 — CHEMINS WINDOWS HARDCODÉS dans settings.py

**Localisation :** `config/settings.py`, lignes ~117-121

**Catégorie :** Problème de portabilité

✅ **CORRIGÉ (D19)** : Bloc DLL enveloppé dans `if sys.platform == 'win32':` — Linux/Mac ignorent complètement ce bloc. `import sys` ajouté en tête de `settings.py`. Chemin toujours configurable via `POSTGRES_BIN_PATH` dans `.env`.
```python
if DATABASES['default']['ENGINE'] == '...postgis':
    if sys.platform == 'win32':  # ← CORRIGÉ
        POSTGRES_BIN = env('POSTGRES_BIN_PATH', default=r"C:\Program Files\PostgreSQL\16\bin")
        GDAL_LIBRARY_PATH = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
        GEOS_LIBRARY_PATH = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')
        os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
```

---

### 🔴 PROBLÈME 4 — CAS 4 vs CAS 5 GOOGLE BUILDINGS NON IMPLÉMENTÉ

**Localisation :** `pipeline/verification_4_couches.py`, méthode `_check_google_buildings()`, lignes ~228-237

**Catégorie :** Limitation externe

**Statut : 🔴 LIMITATION EXTERNE — non corrigeable sans API Google Temporal V1**

Confidence ≥ 0.75 → `FAUX_POSITIF_PRE_EXISTANT` sans vérifier si le bâtiment est antérieur à T1. Risque de faux négatifs pour les constructions récentes (mai 2023 → T1). Correction possible via `GOOGLE/Research/open-buildings-temporal/v1` (collection GEE) — nécessite une intégration supplémentaire hors portant du hackathon.

---

### 🟠 PROBLÈME 5 — DOUBLE DÉFINITION LANGUAGE_CODE et TIME_ZONE

**Localisation :** `config/settings.py`, lignes ~146-148 et ~209-210

**Catégorie :** Dette technique

✅ **CORRIGÉ (C1/C2)** : Doublons supprimés dans `settings.py`. Une seule définition :
- `LANGUAGE_CODE = "fr-fr"` (ligne 209)
- `TIME_ZONE = "Africa/Abidjan"` (ligne 210)

---

### 🟠 PROBLÈME 6 — INCOHÉRENCE StatisticsSerializer / views.py

**Localisation :** `module1_urbanisme/serializers.py` (classe `StatisticsSerializer`) vs `module1_urbanisme/views.py` (méthode `DetectionConstructionViewSet.statistics()`)

**Catégorie :** Bug de sérialisation

✅ **CORRIGÉ (CORRECTIF A10)** : Le champ `StatisticsSerializer` utilise maintenant `detections_sous_condition = serializers.IntegerField()`. La méthode `statistics()` de `views.py` passe `detections_sous_condition=Count(filter=Q(status='sous_condition'))`. L'action `alertes_orange` filtre sur `status='sous_condition'`. Compteur orange API v1 opérationnel.

---

### 🟠 PROBLÈME 7 — django_browser_reload ABSENT de requirements.txt

**Localisation :** `config/settings.py` (INSTALLED_APPS et MIDDLEWARE) vs `requirements.txt`

**Catégorie :** Dépendance manquante

✅ **CORRIGÉ (B3)** : `django-browser-reload>=1.12.0` ajouté dans `requirements.txt` ligne 37. Paquet disponible sur installation fraîche.

---

### 🟠 PROBLÈME 8 — GEE getDownloadURL FORMAT "NPY" NON SUPPORTÉ

**Localisation :** `pipeline/gee_composite.py`, méthode `get_composite()`, ligne ~149

**Catégorie :** Bug confirmé

✅ **CORRIGÉ** : `gee_composite.py` utilise maintenant `"format": "GEO_TIFF"` pour `getDownloadURL`. Lecture via `rasterio.open(io.BytesIO(response.content))`. Phase 4 opérationnelle dès qu'un compte GEE est configuré.

---

### 🟠 PROBLÈME 9 — model_weights.pth INTROUVABLE (TinyCD)

**Localisation :** `pipeline/deep_learning_detector.py`, `module1_urbanisme/data_use/weights/`

**Catégorie :** Incomplétude documentée

✅ **CORRIGÉ (D19)** : Comportement silencieux éliminé. Si `--use-tinycd` est demandé mais que `model_weights.pth` est absent, `run_detection.py` lève maintenant un `CommandError` explicite avec le lien de téléchargement :
```
❌ [TinyCD] model_weights.pth introuvable dans data_use/weights/
   Télécharger levir_best.pth depuis :
   https://github.com/AndreaCodegoni/Tiny_model_4_CD/tree/main/pretrained_models
```
**Note manuelle :** Télécharger le fichier `levir_best.pth` et le renommer en `model_weights.pth` dans `module1_urbanisme/data_use/weights/`.

---

### 🟡 PROBLÈME 10 — core/ NON ENREGISTRÉE dans INSTALLED_APPS

**Localisation :** `config/settings.py`, `core/`

**Catégorie :** Incomplétude structurelle

✅ **CORRIGÉ (C5)** : `"core"` présent dans `INSTALLED_APPS` (ligne 73 de `settings.py`). `manage.py check` confirme 0 issues.

---

### 🟡 PROBLÈME 11 — CHEMINS TIFF HARDCODÉS dans test_pipeline_validation.py

**Localisation :** `tests/test_pipeline_validation.py`, lignes 28-32

**Catégorie :** Tests cassés

✅ **CORRIGÉ (D18)** : Chemins mis à jour — `SENTINEL_DIR` → `sentinel_api_exports`, dates `2024-02-15` / `2025-01-15`, format `B08_{date}.tif`. Tests 2-5 opérationnels.

---

### 🟡 PROBLÈME 12 — BSI SIMPLIFIÉ IDENTIQUE À NDBI

**Localisation :** `pipeline/ndbi_calculator.py`, méthode `calculate_bsi()`, lignes ~93-143

**Catégorie :** Limitation algorithmique documentée

✅ **CORRIGÉ (D9)** : Formule BSI complète `((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02))` implémentée avec paramètre `b02_path: str = None`. Fallback sur `(B11-B08)/(B11+B08)` si B02 absent. Label de formule loggé pour traçabilité.

---

### 🟡 PROBLÈME 13 — MODULES 2 ET 3 ENTIÈREMENT VIDES

**Localisation :** `module2_agroecologie/`, `module3_orpaillage/`

**Catégorie :** Incomplétude attendue (hackathon)

**Gravité :** SELON JURY (potentiellement ÉLEVÉ si évaluation des 3 modules)

**Description :**
`module2_agroecologie` et `module3_orpaillage` sont des squelettes Django avec des fichiers de 60-66 octets (import vide). Aucune logique métier, aucun modèle, aucun template, aucune URL enregistrée.

Ces modules sont présents dans `INSTALLED_APPS` mais n'exposent aucune fonctionnalité.

**Impact :** Si le jury du hackathon évalue les trois modules, seul Module 1 est fonctionnel. Modules 2 et 3 sont vides.

**Contenu prévu (selon la documentation) :**
- Module 2 : surveillance des cultures (NDVI multi-temporel, déforestation, zones humides)
- Module 3 : détection orpaillage illégal (anomalies spectrales dans les rivières, turbidité, mercure)

---

### Tableau récapitulatif des problèmes

| # | Problème | Gravité | Fichier | Impact opérationnel |
|---|---|---|---|---|
| 1 | ~~NameError delta_vv dans SAR~~ | ✅ CORRIGÉ D19 | `sentinel1_sar.py` | `delta_vv = vv_t2 - vv_t1` présent ligne 24 |
| 2 | ~~Source invalide import_microsoft~~ | ✅ CORRIGÉ D17 | `import_microsoft.py` | `source="Google_V3_2023"`, Microsoft_2020 retiré |
| 3 | ~~Chemins Windows hardcodés~~ | ✅ CORRIGÉ D19 | `settings.py` | `sys.platform=='win32'` + `import sys` ajouté |
| 4 | CAS 4 vs 5 Google non implémenté | 🔴 LIMITATION EXTERNE | `verification_4_couches.py` | Requiert Google Temporal V1 API (hors portée) |
| 5 | ~~Double définition LANGUAGE_CODE~~ | ✅ CORRIGÉ C1/C2 | `settings.py` | Une seule définition `fr-fr` / `Africa/Abidjan` |
| 6 | ~~Incohérence StatisticsSerializer~~ | ✅ CORRIGÉ A10 | `serializers.py` / `views.py` | `detections_sous_condition` harmonisé |
| 7 | ~~django_browser_reload manquant~~ | ✅ CORRIGÉ B3 | `requirements.txt` | `django-browser-reload>=1.12.0` ajouté |
| 8 | ~~GEE format "NPY" invalide~~ | ✅ CORRIGÉ | `gee_composite.py` | `format="GEO_TIFF"` + lecture rasterio |
| 9 | ~~model_weights.pth silencieux~~ | ✅ CORRIGÉ D19 | `run_detection.py` | `CommandError` explicite + lien téléchargement |
| 10 | ~~core/ non dans INSTALLED_APPS~~ | ✅ CORRIGÉ C5 | `settings.py` | `"core"` présent ligne 73 |
| 11 | ~~Chemins TIFF obsolètes dans tests~~ | ✅ CORRIGÉ D18 | `test_pipeline_validation.py` | Tests 2-5 opérationnels |
| 12 | ~~BSI = NDBI (formule simplifiée)~~ | ✅ CORRIGÉ D9 | `ndbi_calculator.py` | Vraie formule BSI + b02_path optionnel |
| 13 | Modules 2 et 3 vides | 🟡 HORS PORTÉE | `module2/`, `module3/` | Squelettes hackathon — Module 1 seul fonctionnel |

---

## ✅ SECTION 6 — CE QUE LE PROJET FAIT AUJOURD'HUI (FONCTIONNALITÉS OPÉRATIONNELLES)

---

### 6.1 — Fonctionnalités complètement opérationnelles

---

**Interface web de surveillance (Dashboard)**

Accessible sur `http://127.0.0.1:8000/` après `python manage.py runserver`. Le tableau de bord présente en temps réel : le nombre total de zones cadastrales, le comptage des infractions rouges (`infraction_zonage`), des inspections requises (`sous_condition`), et des conformités. Un graphique donut Chart.js affiche la répartition par niveau d'alerte. Une carte Leaflet interactive superpose les détections colorées (rouge/orange/vert/cyan) sur fond OpenStreetMap, ainsi que les polygones des zones cadastrales colorés selon leur statut. Les 10 dernières détections sont listées avec date, statut, surface et confiance. Tout le contenu est dynamique, chargé depuis la base de données via les vues Django.

---

**Liste et détail des détections**

La page `/detections/` présente toutes les détections filtrables par `status` et `alert_level`. Chaque ligne affiche un badge coloré avec emoji selon le statut. La page `/detections/<id>/` montre le détail complet : carte centrée sur la géométrie, graphique bi-temporel NDBI T1/T2, panneau technique (BSI, surface, confiance, présence Google Buildings), et un formulaire de feedback terrain (confirmation/rejet avec commentaire obligatoire). Un bouton "Vérifier en HD sur Google Maps" génère un lien direct vers Google Maps satellite aux coordonnées exactes.

---

**Zones cadastrales navigables**

La page `/zones/` liste toutes les zones avec leur nombre de détections. La page `/zones/<zone_id>/` affiche la carte de la zone, ses détections associées, et ses métadonnées (type, statut, surface).

---

**API REST complète (v1)**

Disponible sur `/api/v1/`. Endpoints opérationnels :
- `GET /api/v1/detections/` : liste paginée avec filtrage multi-critères (status, alert_level, statut_traitement, zone)
- `PATCH /api/v1/detections/{id}/traiter/` : mise à jour du statut terrain par un agent authentifié
- `GET /api/v1/detections/statistics/` : comptages agrégés par statut et niveau d'alerte
- `GET /api/v1/detections/alertes_rouges/` : filtre sur les infractions, trié par confiance décroissante
- `GET /api/v1/detections/alertes_orange/` : filtre sur les inspections requises
- `GET /api/v1/detections/en_attente/` : filtre sur les détections non traitées
- `GET /api/v1/zones-cadastrales/` : toutes les zones avec géométrie GeoJSON
- `GET /api/v1/dashboard/resume/` : résumé agrégé pour le dashboard
- `GET /api/statistics/` : statistiques JSON pour Chart.js
- `GET /api/detections-geojson/` : FeatureCollection GeoJSON pour Leaflet
- `GET /api/zones-geojson/` : zones cadastrales GeoJSON pour Leaflet

---

**Import du cadastre V10**

La commande `python manage.py import_cadastre` importe automatiquement les 200+ zones cadastrales de Treichville depuis le fichier GeoJSON local. Elle détecte les zones déjà présentes (update_or_create par zone_id) et gère les erreurs zone par zone. Le mode `--dry-run` permet de prévisualiser sans écrire en base.

---

**Import des empreintes Google Open Buildings**

La commande `python manage.py import_google_buildings --from-geojson <fichier>` importe les empreintes de bâtiments connus (mode offline, sans connexion GEE). Filtrage par niveau de confiance (défaut 0.65), import par `bulk_create` de 500 en 500 dans des transactions atomiques.

---

**Import des images Sentinel-2 (multi-source)**

La commande `python manage.py import_sentinel_api --date 2024-01-29` télécharge automatiquement les images depuis trois sources en cascade :
1. Sentinel Hub (si clé API configurée) — composite médian sans nuage côté serveur
2. CDSE Copernicus (gratuit, sans clé) — catalogue STAC public, lecture directe des COG
3. Microsoft Planetary Computer (si clé configurée)

Les bandes B04, B08, B11 et SCL sont sauvegardées en TIFF GeoTIFF géoréférencés (WGS84, LZW), et un enregistrement `ImageSatellite` est créé en base avec les chemins absolus.

---

**Pipeline NDBI empirique**

La commande `python manage.py run_detection --date-t1 2024-01-29 --date-t2 2025-01-13` détecte les nouvelles constructions, terrassements, et démolitions par comparaison d'indices NDBI bi-temporels. La chaîne complète — calcul spectral, masques nuages/eau/végétation, extraction de régions connexes, vérification 4 couches cadastrales — produit des enregistrements `DetectionConstruction` en base.

---

**Pipeline K-Means IA**

La même commande avec `--use-ai` active le détecteur K-Means. La segmentation multispectrale (NDBI + NDVI + texture Sobel) est plus robuste face aux matériaux locaux ivoiriens (tôle ondulée, béton non peint). Les masques SCL et NDWI synthétique filtrent les pixels nuageux et aquatiques.

---

**Score de confiance dynamique**

Chaque détection reçoit un score de confiance calculé sur 4 critères pondérés : intensité du changement NDBI (40%), valeur BSI (20%), surface de la zone (20%), absence de nuages (20%). Ce score alimente la sérialisation du `priority_score` (0-100) exposé dans l'API REST.

---

**Masques automatiques de filtrage**

Trois masques sont appliqués automatiquement pour réduire les faux positifs :
- Masque nuages SCL : classes 3 (ombre nuage), 6 (eau SCL), 8 (nuage moyen), 9 (nuage dense), 10 (cirrus)
- Masque eau proxy : pixels NDBI T2 < -0.15 (sans B03)
- Masque végétation dense : pixels NDVI T2 > 0.4

---

**Détection des démolitions**

La détection bidirectionnelle est active : `demolished = (ndbi_t1 > 0.25) & (ndbi_t2 < 0.05)`. Les démolitions sont classées avec `alert_level = 'orange'` et le type `demolition`, permettant de suivre les bâtiments abattus.

---

**Rejet de la micro-détection**

Toute détection de surface < 200m² est automatiquement filtrée avant la vérification 4 couches. Cette limite correspond à la résolution physique de Sentinel-2 (2 pixels × 10m × 10m), en dessous de laquelle la fiabilité est insuffisante.

---

**Export CSV GPS**

Le script `python scripts/export_detections_gps.py` génère `exports/export_detections_gps.csv` avec toutes les colonnes (latitude, longitude, status, alert_level, NDBI, surface, confiance, zone cadastrale) pour partage avec les agents terrain ou import dans un SIG.

---

**Interface d'administration Django**

Accessible sur `/admin/`, l'interface admin permet la consultation et modification directe des 4 modèles avec support des cartes géographiques interactives (`GISModelAdmin`).

---

### 6.2 — Fonctionnalités partiellement implémentées

---

**Masque eau NDWI (partiel)**

L'infrastructure est complète (`b03_downloader.py`, `b03_synthesizer.py`, `calculate_ndwi_from_paths()`). Elle est activée par `--download-b03`. Sans B03 réel téléchargé, le masque eau proxy (NDBI < -0.15) est utilisé — moins précis mais suffisant pour exclure les zones lagunaires évidentes. La vraie bande B03 nécessite une connexion CDSE ou Sentinel Hub.

---

**Scoring IA local HuggingFace (mode local)**

Activé par `--use-hf-ai`, le module `HuggingFaceAIClient` fonctionne entièrement en local via des règles spectrales pondérées (`_local_ai_score()`). Le mode cloud (API HuggingFace distante) est volontairement désactivé depuis le 22/03/2026 (modèles inadaptés au contexte ivoirien).

---

**GEE Split-screen (script prêt, déploiement manuel requis)**

Le script JavaScript `gee_split_app.js` est complet et fonctionnel. Il doit être copié dans l'éditeur code.earthengine.google.com, publié comme "App" publique, et son URL mise à jour dans `templates/module1/detection_detail.html` (remplacement du placeholder `VotreCompteGEE`). Une fois déployé, le bouton "Voir T1/T2 sur GEE" dans les pages détection affichera le split-screen interactif.

---

**TinyCD Deep Learning (architecture prête, poids manquants)**

Le réseau de neurones TinyCD (EfficientNet-B4 siamois) est entièrement implémenté dans `tinycd_models/`. Le détecteur `DeepLearningDetector` est fonctionnel si le fichier `model_weights.pth` est présent dans `data_use/weights/`. Sans ce fichier (gitignored), le mode `--use-tinycd` retourne un masque vide silencieusement.

---

### 6.3 — Fonctionnalités prévues mais non implémentées

---

**SAR Sentinel-1 (stub structuré)**

`pipeline/sentinel1_sar.py` expose l'interface future : `evaluate_sar_backscatter_delta()`, `fetch_and_evaluate_sar_for_bbox()`, `merge_optical_and_sar_masks()`. L'argument `--use-sar` est défini dans `run_detection.py`. Bloqué par l'absence d'un token d'entreprise Sentinel Hub pour accéder aux bandes S1-GRD.

**Tâches asynchrones Celery**

`celery==5.3.6` et `redis==5.0.3` sont dans `requirements.txt` avec des commentaires "file d'attente IA". Aucun task Celery n'est défini dans le projet actuel.

**Export PDF WeasyPrint**

`WeasyPrint>=60.0` est dans `requirements.txt`. Aucune vue n'utilise WeasyPrint.

**Modules 2 (Agroécologie) et 3 (Orpaillage)**

Squelettes Django vides. Aucune fonctionnalité implémentée.

---

## ⚠️ SECTION 7 — LIMITES ET CONTRAINTES ACTUELLES DU PROJET

---

### Limite 1 — Résolution physique à 10m/pixel (contrainte matérielle fondamentale)

La résolution spatiale des bandes B08 et B11 de Sentinel-2 est de 10 à 20 mètres par pixel. Cette contrainte physique est absolue et indépassable sans changer de capteur satellite. Elle entraîne les impossibilités suivantes, documentées dans `analyse_ia_et_earth.md` :

Les extensions en hauteur (ajout d'un étage) sont physiquement indétectables car la surface au sol ne change pas. Les murs de clôture (largeur < 2m) sont trop étroits pour occuper un pixel entier. Les surélévations partielles (vérandas, auvents de 1-3m) sont sous la limite de résolution. Toute structure de surface < 100m² (1 pixel) sera ignorée.

Aucune amélioration algorithmique ou IA ne peut compenser ce plafond physique. Pour détecter ces cas, il faudrait des images à très haute résolution (0.3-1m/pixel, comme celles de Planet Labs ou Maxar Technologies), disponibles uniquement avec des contrats commerciaux coûteux.

---

### Limite 2 — Couverture nuageuse abondante à Abidjan (contrainte climatique)

Abidjan subit deux saisons des pluies par an (avril-juillet et septembre-novembre) avec une couverture nuageuse quasi-permanente pouvant atteindre 80-90% des jours. Les images Sentinel-2 optiques sont inutilisables sous les nuages.

Le masque SCL compense partiellement en excluant les pixels nuageux, mais si l'image entière est couverte, la détection est impossible. Le mode K-Means est plus robuste que le seuillage NDBI pur, mais reste bloqué par les nuages. La solution prévue (SAR Sentinel-1 anti-nuage) n'est pas opérationnelle. La sélection de T1 et T2 en saison sèche (janvier) atténue le problème mais ne l'élimine pas.

---

### Limite 3 — Zone géographique fixe Treichville uniquement

La bounding box `TREICHVILLE_BBOX = {"min_lon": -4.03001, "min_lat": 5.28501, "max_lon": -3.97301, "max_lat": 5.32053}` est hardcodée dans 5 fichiers distincts : `sentinel_data_fetcher.py`, `gee_composite.py`, `verification_4_couches.py`, `import_google_buildings.py`, et `import_microsoft.py`. Étendre le système à une autre zone géographique (Yopougon, Cocody, Abobo...) nécessite de modifier ces 5 fichiers et de réimporter toutes les données de référence (cadastre, empreintes bâtiments).

---

### Limite 4 — PostGIS requis pour les requêtes spatiales (contrainte infrastructure)

Les opérations `ST_DWithin`, `ST_Contains`, `ST_Intersects` dans `verification_4_couches.py` nécessitent impérativement l'extension PostGIS sur PostgreSQL. En mode SQLite (développement), ces requêtes échouent ou retournent des résultats inexacts (SpatiaLite non configuré). Toute la couche 1 (Google Buildings) et couche 4 (cadastre) de la vérification sont non fonctionnelles sans PostGIS.

---

### Limite 5 — Poids TinyCD non adaptés au contexte africain (contrainte algorithme)

Le modèle TinyCD est entraîné sur le jeu de données LEVIR-CD (États-Unis, résolution 0.5m/pixel, bâtiments à toit plat, matériaux occidentaux). Les différences avec Treichville sont fondamentales : résolution 20× inférieure (10m vs 0.5m), matériaux de construction différents (tôle ondulée galvanisée, béton non peint), densité urbaine informelle sans géométrie régulière. Le seuil de détection 0.30 n'est pas validé sur vérité terrain ivoirienne. Les faux positifs et faux négatifs spécifiques à ce contexte sont inconnus.

---

### Limite 6 — CAS 4 vs CAS 5 Google Buildings (contrainte logique)

Tout bâtiment Google confidence ≥ 0.75 est rejeté comme pré-existant (Section 5, Problème 4). Cela signifie que les constructions rapides réalisées entre mai 2023 et janvier 2024 (la période la plus concernée par une politique de répression des constructions illégales) sont systématiquement ignorées si Google les a cataloguées. Ce biais est documenté dans le code mais non corrigé.

---

### Limite 7 — Pas d'authentification avancée pour les agents terrain

Le système utilise le modèle d'authentification standard Django. Il n'y a pas de gestion des rôles (agent terrain vs superviseur vs analyste), pas de journal d'audit des modifications, pas de signature numérique des confirmations terrain. L'action `traiter` est protégée par `IsAuthenticated` mais n'implémente pas de contrôle de permission granulaire.

---

### Limite 8 — Performances sur grande surface

Le calcul NDBI opère sur l'intégralité de la bounding box Treichville (~60km² à 10m/pixel ≈ 600×600 pixels). Pour une zone plus grande, les arrays numpy deviendraient trop volumineux pour la mémoire disponible (16 Go RAM). La version actuelle n'implémente pas de découpage en tuiles (tiling).

---

### Limite 9 — Pas de versioning des détections

Chaque lancement de `run_detection` avec `--clear-previous` supprime toutes les détections précédentes. Il n'y a pas de système de versioning permettant de comparer les résultats entre deux lancements du pipeline, d'historiser les faux positifs confirmés, ou de suivre l'évolution d'une construction dans le temps.

---

### Limite 10 — BSI non discriminant (contrainte algorithmique)

La formule BSI simplifiée est identique à NDBI (Problème 12). La discrimination entre "terrassement de sol nu" et "construction" est très faible. Les types `soil_activity` et `new_constructions` sont donc difficiles à distinguer spectrallement, ce qui peut introduire une ambiguïté dans la classification finale.

---

## 🚀 SECTION 8 — GUIDE DE PRISE EN MAIN RAPIDE

---

### 8.1 — Prérequis système

Avant de commencer, s'assurer d'avoir :
- Python 3.10 ou supérieur installé
- Sur Windows : PostgreSQL 16 avec l'extension PostGIS installée (recommandé pour les requêtes spatiales)
- Git pour cloner le dépôt
- Connexion internet (pour le téléchargement des images Sentinel-2 via CDSE gratuit)
- Au minimum 4 Go de RAM libre (8 Go recommandés pour le traitement des images)

---

### 8.2 — Installation

**Étape 1 — Cloner le dépôt**

Cloner le dépôt dans un répertoire local. Se positionner dans le répertoire `SIADE_hackathon`.

**Étape 2 — Créer l'environnement virtuel**

Sur Windows, exécuter le script `install_venv.ps1` qui crée un venv avec héritage des packages système (GDAL/GEOS). Il installe ensuite les packages satellites (sentinelhub, earthengine-api, pystac-client).

Alternativement : créer un venv standard, activer, puis `pip install -r requirements.txt`, suivi de `pip install django-browser-reload` (manquant dans requirements.txt).

**Étape 3 — Configurer l'environnement**

Copier `.env.example` vers `.env`. Remplir au minimum :
- `SECRET_KEY` : générer une clé via la commande Django dédiée
- `DEBUG=True` pour le développement
- `DATABASE_URL` : laisser vide pour SQLite, ou renseigner `postgis://user:password@localhost:5432/nom_base` pour PostGIS

Les clés API satellites (SENTINEL_HUB, GEE, MICROSOFT_PC) sont optionnelles. CDSE Copernicus fonctionne gratuitement sans clé.

**Étape 4 — Appliquer les migrations**

`python manage.py migrate` crée toutes les tables en base de données. Sur PostGIS, cette commande crée également les extensions géographiques.

---

### 8.3 — Premier lancement minimal (mode développement SQLite)

**Import du cadastre :**
`python manage.py import_cadastre`

Importe les zones cadastrales depuis le fichier GeoJSON local. Résultat attendu : N zones créées.

**Lancement du serveur web :**
`python manage.py runserver`

Ouvrir `http://127.0.0.1:8000/` dans un navigateur. Le dashboard doit s'afficher avec les zones cadastrales importées.

---

### 8.4 — Pipeline de détection complet

**Télécharger les images Sentinel-2 T1 :**
`python manage.py import_sentinel_api --date 2024-01-29`

**Télécharger les images Sentinel-2 T2 :**
`python manage.py import_sentinel_api --date 2025-01-13`

**Importer les empreintes Google Open Buildings :**
`python manage.py import_google_buildings --from-geojson <chemin_vers_fichier.geojson>`

**Lancer la détection (mode K-Means recommandé) :**
`python manage.py run_detection --date-t1 2024-01-29 --date-t2 2025-01-13 --use-ai --use-hf-ai`

**Vérifier les résultats :**
Navigateur → `http://127.0.0.1:8000/` → Les détections apparaissent sur la carte.

---

### 8.5 — Commandes utiles de diagnostic

**Vérifier la configuration Django :**
`python manage.py check`

**Compter les enregistrements en base :**
`python manage.py shell -c "from module1_urbanisme.models import DetectionConstruction; print(DetectionConstruction.objects.count())"`

**Lancer les tests unitaires :**
`python manage.py test module1_urbanisme`

**Script de diagnostic complet :**
`python scripts/auto_fix_and_verify.py` (nécessite le serveur en cours d'exécution sur le port 8001)

**Export CSV des détections GPS :**
`python scripts/export_detections_gps.py`

---

### 8.6 — Erreurs fréquentes et solutions

| Erreur | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'django_browser_reload'` | Absent de requirements.txt | `pip install django-browser-reload` |
| `CPLE_AppDefined PROJ...` dans les logs | Conflit PROJ rasterio/PostgreSQL | Normal, silencié par settings.py — aucune action |
| `RuntimeError: AUCUNE SOURCE DE DONNÉES DISPONIBLE` | Pas de TIFF dans sentinel_api_exports/ ET CDSE inaccessible | Vérifier connexion internet ou placer les TIFF manuellement |
| `ImproperlyConfigured: SpatialiteExtension` | SQLite sans SpatiaLite, requête spatiale appelée | Configurer PostGIS ou éviter les requêtes ST_DWithin en mode SQLite |
| `FileNotFoundError: model_weights.pth` | Poids TinyCD absents | Télécharger `levir_best.pth` depuis GitHub TinyCD, renommer en `model_weights.pth`, placer dans `data_use/weights/` |
| `ValueError: Moins de 2 images en base` | import_sentinel non exécuté | Lancer `import_sentinel_api` pour T1 et T2 |
| Dashboard affiche 0 détections | Pipeline non lancé ou --dry-run | Lancer `run_detection` sans `--dry-run` |
| Carte Leaflet vide | PostGIS absent, requêtes GeoJSON échouent | Passer en mode PostGIS ou déboguer via `/api/detections-geojson/` |

---

### 8.7 — Options avancées de run_detection

| Combinaison | Usage recommandé |
|---|---|
| Sans flag | Mode NDBI pur, rapide, déterministe |
| `--use-ai` | Production, meilleure précision, +10 secondes |
| `--use-ai --use-hf-ai` | Production améliorée, scoring IA local |
| `--use-ai --download-b03` | Avec masque eau NDWI précis (nécessite CDSE) |
| `--use-tinycd` | Expérimental, nécessite `model_weights.pth` |
| `--dry-run` | Prévisualisation sans écriture en base |
| `--clear-previous` | Effacer les anciennes détections avant nouvelle analyse |
| `--threshold-built 0.15` | Seuil plus bas pour zones à matériaux pauvres |

---

## 🏁 SECTION 9 — SYNTHÈSE GLOBALE

---

CIV-EYE Module 1 est un système de surveillance du bâti par satellite conçu pour détecter et qualifier automatiquement les constructions illégales dans le quartier de Treichville à Abidjan, Côte d'Ivoire. Le projet répond à un besoin réel et documenté : les agents cadastraux ne peuvent pas surveiller manuellement un territoire urbain dense en mutation rapide, et les constructions informelles sur zones interdites (lits de rivières, emprises portuaires, servitudes) constituent un risque pour la sécurité publique et la planification urbaine.

L'architecture choisie est cohérente et adaptée au contexte. Django constitue un socle solide pour la gestion des données géospatiales (PostGIS) et l'exposition d'une API REST. La chaîne de traitement — acquisition multi-source Sentinel-2, calcul d'indices spectraux NDBI/BSI/NDVI, segmentation K-Means avec features spectrales et texturales, vérification 4 couches croisant Google Open Buildings V3 et cadastre V10 — est logiquement construite et tient compte des spécificités ivoiriennes (seuils NDBI abaissés à 0.10 pour les matériaux locaux, masque NDVI pour la végétation dense). Les 10 correctifs documentés (A1-A9, L1-L6) témoignent d'un travail de débogage rigoureux conduisant à un pipeline techniquement solide.

La résilience multi-source est un point fort majeur : le projet fonctionne entièrement sans aucune clé API payante grâce à la source CDSE Copernicus gratuite, rendant le système autonome pour l'acquisition des données satellites. L'interface web "Cyber Tactique" est visuellement soignée, fonctionnelle, et intègre des fonctionnalités pratiques pour les agents terrain (bouton Google Maps HD, formulaire de feedback, export CSV GPS).

Les limites identifiées se répartissent en deux catégories. Les limites fondamentales irréconciliables : la résolution physique de 10m/pixel de Sentinel-2 rend physiquement impossible la détection des extensions en hauteur, murs de clôture, et constructions < 100m². La couverture nuageuse d'Abidjan en saison des pluies limite l'utilisation effective aux mois de saison sèche (décembre-mars). Ces contraintes sont inhérentes au choix du capteur et ne peuvent être levées qu'avec un changement de source de données (images commerciales 0.5m). Les limites corrigeables : le bug NameError dans `sentinel1_sar.py`, le rejet systématique des constructions post-mai 2023 (CAS 4 vs CAS 5 Google Buildings non implémenté), les chemins Windows hardcodés bloquant le déploiement Linux, et le format GEE "NPY" invalide rendant le compositing multi-temporel inopérant constituent des points de blocage concrets à résoudre en priorité.

La maturité du projet est celle d'un prototype hackathon avancé. Module 1 est complet, démontrable, et fonctionnel pour la zone pilote de Treichville. Il peut s'exécuter de bout en bout sur une machine Windows avec PostGIS et produire des alertes géolocalisées exploitables par des agents terrain. Les deux modules restants (Agroécologie, Orpaillage) sont des squelettes vides qui constituent le travail principal restant pour compléter la vision tri-modulaire initiale de CIV-EYE.

Les quatre actions prioritaires pour porter ce projet en production sont : (1) corriger le bug `delta_vv` dans `sentinel1_sar.py` et implémenter la vérification Google Temporal V1 (CAS 5) pour éliminer les faux négatifs sur constructions post-2023 ; (2) remplacer les chemins Windows hardcodés par des variables d'environnement pour permettre le déploiement Linux/Docker ; (3) corriger le format GEE "NPY" en "GEO_TIFF" pour activer le compositing multi-temporel ; (4) ajouter `django-browser-reload` dans `requirements.txt` pour permettre une installation fraîche sans erreur.

---

*Fin du rapport d'analyse — CIV-EYE Module 1 — Mars 2026*
*Généré par analyse exhaustive de l'intégralité du code source (corpus `silvercross2021-web/ci-eye360`)*
