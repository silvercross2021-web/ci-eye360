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

### Fichiers partagés (modifier avec accord de l'équipe)

| Fichier | Impact si modifié |
|---|---|
| `config/settings.py` | Configuration globale Django (GDAL, PostGIS, INSTALLED_APPS) — touche tout le projet |
| `config/urls.py` | Routes de toute l'application — peut casser les modules existants |
| `requirements.txt` | Dépendances Python partagées — ajouter manuellement, jamais de pip freeze |
| `templates/module1/base.html` | Thème "Cyber Tactique" dark mode — ne pas réécrire les variables CSS `:root` |

---

## 2. Architecture technique du Module 1

Comprendre comment Module 1 fonctionne est indispensable avant de créer M2 ou M3.

### Les 4 modèles de données

**`ZoneCadastrale`** — Représente une zone du plan d'urbanisme de Treichville. Contient la géométrie (polygone PostGIS), le nom de la zone, son type (résidentiel, portuaire, industriel…) et son statut (constructible, conditionnel, interdit). 19 zones sont importées depuis le fichier GeoJSON du plan V10.

**`ImageSatellite`** — Stocke les métadonnées d'une image Sentinel-2. Ne contient pas les pixels mais les chemins vers les fichiers TIF sur le disque (bandes B04, B08, B11 et le masque SCL). Deux images sont en base : T1 = 15 février 2024, T2 = 15 janvier 2025.

**`MicrosoftFootprint`** (nom historique, données Google) — Contient les 39 810 empreintes de bâtiments connus issus de Google Open Buildings V3. Sert à identifier les bâtiments pré-existants pour filtrer les faux positifs dans le pipeline de détection.

**`DetectionConstruction`** — Résultat final du pipeline. Chaque enregistrement représente un changement détecté entre T1 et T2, avec sa géométrie PostGIS, ses valeurs NDBI, sa surface estimée, et sa classification (infraction_zonage / sous_condition / conforme / surveillance_preventive). 729 détections sont actuellement en base.

### Le pipeline de traitement (5 étapes)

Le pipeline est déclenché par `python manage.py run_detection` ou `python manage.py pipeline_check`. Il suit toujours les mêmes 5 étapes :

**Étape 1 — Acquisition.** Les fichiers TIF Sentinel-2 sont lus depuis `data_use/sentinel_api_exports/`. S'ils n'existent pas, ils peuvent être téléchargés via l'API Copernicus CDSE ou Sentinel Hub grâce à `sentinel_data_fetcher.py`.

**Étape 2 — Indices spectraux.** Le fichier `ndbi_calculator.py` calcule les indices sur les bandes Sentinel-2. Le NDBI (Normalized Difference Built-up Index) sur T1 et T2 permet de mesurer la densité de surfaces bâties. Le BSI (Bare Soil Index) détecte les terrassements. Le NDVI masque la végétation. Le masque SCL supprime les zones nuageuses et l'eau (lagune Ébrié).

**Étape 3 — Détection IA.** Soit K-Means (recommandé, sans GPU) compare les clusters spectraux entre T1 et T2 pour identifier les pixels qui sont passés de "sol" à "bâti". Soit TinyCD (réseau de neurones PyTorch) analyse les paires d'images directement.

**Étape 4 — Extraction des régions.** Les pixels détectés sont regroupés en composantes connexes (zones géographiques contiguës). Chaque région trop petite (moins de 2 pixels, soit moins de 200m²) est filtrée. Chaque région est convertie de coordonnées pixel en coordonnées GPS WGS84.

**Étape 5 — Vérification 4 couches.** Chaque région candidate passe par 4 filtres anti-faux-positifs, gérés par `verification_4_couches.py` :
- Couche 1 : si un bâtiment Google V3 avec confiance ≥ 0.75 existe déjà à cet endroit → rejeté comme faux positif
- Couche 2 : la zone cadastrale détermine le statut (interdit → rouge, conditionnel → orange, constructible → vert)
- Couche 3 : cohérence des valeurs spectrales T1/T2/BSI — filtre les incohérences
- Couche 4 : surface minimale et coordonnées dans la bounding box de Treichville

### Les management commands

Chaque opération d'import/export/détection est une commande Django dans `module1_urbanisme/management/commands/`. Toutes les commandes acceptent `--dry-run` pour un aperçu sans modification de la base.

| Commande | Rôle |
|---|---|
| `import_cadastre` | Lit le GeoJSON des zones et crée les 19 `ZoneCadastrale` |
| `import_sentinel` | Lit les TIF locaux et crée les enregistrements `ImageSatellite` |
| `import_sentinel_api` | Télécharge les images depuis CDSE/SH et crée les TIF + `ImageSatellite` |
| `import_google_buildings` | Interroge GEE et importe les 39 810 empreintes Google V3 |
| `import_google_temporal_v1` | Analyse les snapshots GEE Temporal V1 (pas importable en masse) |
| `export_footprints` | Sauvegarde les empreintes en GeoJSON (backup) |
| `pipeline_check` | 2 volets : vérification système puis détection |
| `run_detection` | Pipeline de détection complet (K-Means ou TinyCD) |

### L'API REST

Toutes les routes Module 1 sont dans `module1_urbanisme/urls.py` et branchées dans `config/urls.py` sous le préfixe `/api/v1/`. Les endpoints principaux sont `/api/v1/zones-cadastrales/`, `/api/v1/detections/`, `/api/v1/detections/statistics/` et `/api/v1/dashboard/resume/`. Les vues web HTML (dashboard, liste des détections, détail) sont dans `views_web.py` et accessibles via `/`, `/detections/` et `/zones/`.

---

## 3. Guide — Créer le Module 2 (Agroécologie)

Le dossier `module2_agroecologie/` existe déjà dans le projet avec un squelette Django vide. Voici les étapes pour le développer.

### Étape 1 — Définir les modèles dans `module2_agroecologie/models.py`

S'inspirer des 4 modèles de Module 1 et les adapter au contexte agroécologique. Le module a besoin d'au moins 3 modèles :

- **Un modèle de zone géographique** (équivalent de `ZoneCadastrale`) — représente une zone agricole ou forestière surveillée. Champs recommandés : nom, type de culture, région administrative, géométrie PostGIS (PolygonField avec srid=4326).

- **Un modèle d'image satellite** — peut réutiliser directement `ImageSatellite` de Module 1 si les mêmes images couvrent la zone, ou créer un modèle dédié avec les mêmes champs (date_acquisition, bands JSONField pour les chemins TIF, classification_map pour le SCL).

- **Un modèle d'alerte** (équivalent de `DetectionConstruction`) — représente un événement détecté (déforestation, changement de culture, sécheresse…). Champs recommandés : zone (ForeignKey), géométrie PostGIS, valeurs NDVI T1/T2, type d'alerte, niveau de confiance, date de détection.

**Important :** toujours importer depuis `django.contrib.gis.db` (pas `django.db`) pour avoir accès aux champs géospatiaux. Toujours utiliser `srid=4326` (WGS84) pour la cohérence avec le reste du projet.

### Étape 2 — Vérifier que le module est dans INSTALLED_APPS

Ouvrir `config/settings.py` et vérifier que `module2_agroecologie` est bien dans la liste `INSTALLED_APPS`. Il devrait déjà y être dans le squelette.

### Étape 3 — Créer les migrations

Une fois les modèles définis, générer les migrations avec `python manage.py makemigrations module2_agroecologie` puis les appliquer avec `python manage.py migrate`.

### Étape 4 — Créer le pipeline de calcul dans `module2_agroecologie/pipeline/`

S'inspirer de `module1_urbanisme/pipeline/ndbi_calculator.py`. Le fichier de base pour M2 est un calculateur NDVI (Normalized Difference Vegetation Index) qui lit deux fichiers TIF (B04 et B08) et retourne un tableau numpy. La formule est `NDVI = (B08 − B04) / (B08 + B04)`. Valeurs entre -1 et +1 — végétation dense ≈ +0.6, sol nu ≈ 0, eau ≈ -0.3.

Il est aussi possible de réutiliser directement `NDBICalculator` de Module 1 qui contient déjà `calculate_ndvi()`, `extract_change_regions()`, et `apply_scl_mask()`. Il n'est pas nécessaire de réécrire ces fonctions.

### Étape 5 — Créer la management command dans `module2_agroecologie/management/commands/`

Créer un fichier `run_detection_agro.py` en s'inspirant de `run_detection.py` de Module 1. La structure est toujours la même : une classe `Command` qui hérite de `BaseCommand`, une méthode `add_arguments` pour les options CLI, et une méthode `handle` qui exécute le pipeline. Les étapes : récupérer les images → calculer NDVI T1 et T2 → détecter les zones de perte de végétation → extraire les régions → sauvegarder les alertes en base.

### Étape 6 — Créer `module2_agroecologie/urls.py` et brancher dans `config/urls.py`

Créer un fichier `urls.py` dans le module 2 avec les routes API (DRF Router) et/ou les vues web. Puis dans `config/urls.py`, ajouter l'inclusion sous un préfixe dédié — par exemple `/api/v2/` pour l'API REST et `/module2/` pour l'interface web.

### Étape 7 — Créer les tests dans `test_special/test_AGRO.py`

S'inspirer de `test_PIPE.py` ou `test_DB.py`. Le fichier doit respecter exactement le même format que les autres suites : fonctions `ok()`, `fail()`, `warn()`, et un résumé final `OK: X | FAIL: Y | TOTAL: Z`. Une fois le fichier créé, ajouter `"AGRO"` dans la liste `ALL_SUITES` de `run_tests.py` pour qu'il soit inclus dans les tests globaux.

---

## 4. Guide — Créer le Module 3 (Orpaillage)

Le principe est identique au Module 2. La différence principale réside dans les indices spectraux utilisés.

L'orpaillage illégal dans les rivières se caractérise par une turbidité anormale de l'eau (eau boueuse à cause des terrassements) et la présence de sol nu et de boue en bordure des cours d'eau. Les indices recommandés pour la détection sont :

- **MNDWI** (Modified NDWI) = (B03 − B11) / (B03 + B11) → mesure la turbidité de l'eau. Une valeur très élevée indique une eau chargée en sédiments.
- **NDTI** (Normalized Difference Turbidity Index) = (B04 − B03) / (B04 + B03) → turbidité par différence rouge-vert.
- Combinaison B11 élevé + NDVI bas = sol nu ou boue en zone normalement végétalisée → indice fort d'orpaillage.

La structure de dossiers suggérée pour Module 3 est la même que Module 2, avec un `models.py` contenant un modèle de cours d'eau surveillé, un modèle d'image satellite, et un modèle d'alerte d'orpaillage. Le pipeline va dans `module3_orpaillage/pipeline/` et les commandes dans `module3_orpaillage/management/commands/`.

---

## 5. Indices spectraux de référence

| Indice | Formule | Bandes utilisées | Module | Ce qu'il détecte |
|---|---|---|---|---|
| **NDBI** | (B11 − B08) / (B11 + B08) | SWIR1, NIR | M1 | Surfaces bâties (toits, béton, tôle) |
| **BSI** | (B11 + B04 − B08) / (B11 + B04 + B08) | SWIR1, Rouge, NIR | M1 | Sol nu, terrassements |
| **NDVI** | (B08 − B04) / (B08 + B04) | NIR, Rouge | M1 + M2 | Végétation verte, couvert forestier |
| **NDWI** | (B03 − B08) / (B03 + B08) | Vert, NIR | M1 + M2 | Eau, surfaces irriguées |
| **BUI** | NDBI − NDVI | — | M1 | Built-Up Index — filtre la végétation des zones bâties |
| **MNDWI** | (B03 − B11) / (B03 + B11) | Vert, SWIR1 | M3 | Turbidité des rivières |
| **NDTI** | (B04 − B03) / (B04 + B03) | Rouge, Vert | M3 | Turbidité par couleur de l'eau |

---

## 6. Conventions de développement

### Nommage des fichiers et classes

Les modèles Django sont nommés en PascalCase (ex: `AlerteDeforestation`, `ZoneAgricole`, `CoursDEau`). Les commandes management sont nommées en snake_case avec un préfixe d'action (ex: `run_detection_agro.py`, `import_zones_agro.py`, `export_alertes.py`). Les fichiers de pipeline sont nommés selon leur fonction principale (ex: `ndvi_calculator.py`, `turbidite_calculator.py`).

### Règles PostGIS

Toujours importer les modèles depuis `django.contrib.gis.db` et non `django.db`. Toujours utiliser `srid=4326` (WGS84) pour tous les champs géométriques — c'est la référence spatiale utilisée dans tout le projet et les données Google/Copernicus. Ne pas utiliser d'autres SRID sans conversion explicite.

### Règles rasterio

Toujours lire les fichiers TIF en utilisant `rasterio.open()` dans un bloc `with`. Toujours convertir les tableaux numpy en `float` avant les calculs (`astype(float)`). Toujours protéger contre la division par zéro avec `np.where(denominateur == 0, 0.0, ...)`. Toujours clipper les résultats entre -1.0 et +1.0. Ne jamais utiliser `'EPSG:4326'` comme CRS dans rasterio — préférer la chaîne proj4 `'+proj=longlat +datum=WGS84 +no_defs'` pour éviter les conflits avec la base PROJ de PostgreSQL sur Windows.

### Règles pour les management commands

Toujours hériter de `BaseCommand`. Toujours implémenter `--dry-run` pour tester sans écriture en base. Utiliser `self.stdout.write(self.style.SUCCESS(...))` pour les succès, `self.style.ERROR(...)` pour les erreurs, `self.style.WARNING(...)` pour les avertissements. Ne jamais utiliser `print()` dans une commande.

---

## 7. Workflow Git

### Règles absolues

- Ne jamais faire `git push -f` sur `main` — supprime le code de façon irréversible
- Ne jamais commiter `.env`, `db.sqlite3`, `venv/`, ou des fichiers `.pth` supérieurs à 50 Mo
- Ne jamais faire `pip freeze > requirements.txt` — ajouter les dépendances manuellement ligne par ligne
- Ne jamais modifier les migrations d'un autre module sans accord explicite
- Toujours travailler sur une branche, jamais directement sur `main`

### Nomenclature des branches

Les branches suivent le format `type/module-description`. Exemples : `feature/module2-detection-ndvi`, `feature/module3-turbidite-orpaillage`, `bugfix/module1-correction-seuil-ndbi`, `hotfix/fix-crash-serializer`.

### Cycle de travail quotidien

Au début de chaque session, récupérer les modifications de `main` (`git pull origin main`), créer ou basculer sur sa branche de travail, commiter régulièrement avec des messages clairs, puis pousser sa branche et créer une Pull Request sur GitHub avant de fusionner sur `main`.

### Format des messages de commit

Les messages suivent le format `type(module): description`. Les types disponibles sont `feat` (nouvelle fonctionnalité), `fix` (correction de bug), `docs` (documentation), `test` (tests), `refactor` (refactorisation sans changement de comportement), et `chore` (maintenance). Exemples : `feat(mod2): ajout modèle AlerteDeforestation PostGIS`, `fix(mod1): correction seuil NDBI pour tôle ivoirienne`, `docs: mise à jour CONTRIBUTING.md`.

### Résoudre un conflit Git

Basculer sur sa branche, faire `git pull origin main` pour récupérer les nouveautés, résoudre les blocs de conflit `<<<< ==== >>>>` dans l'éditeur, puis commiter la résolution et repousser.

---

## 8. Vérifications obligatoires avant tout push

Avant de pousser quoi que ce soit sur GitHub, trois vérifications sont obligatoires :

1. **`python manage.py check`** — doit retourner 0 erreur. Si des erreurs apparaissent, elles doivent être corrigées avant tout push.

2. **`python run_tests.py --fast`** — doit retourner 0 FAIL. Les WARNs sont acceptables (4 en config dev), mais aucun FAIL n'est toléré.

3. **`python manage.py pipeline_check --verify-only`** — vérifie que les 8 prérequis système (Django, images, TIF, V3, cadastre, TinyCD, GEE) sont tous verts.

---

## 9. Ajouter des tests pour son module

Créer un fichier `test_special/test_NOMDUMODULE.py` en s'inspirant exactement de `test_PIPE.py` ou `test_DB.py`. Le fichier doit impérativement respecter le même format que les autres suites — les fonctions `ok()`, `fail()`, `warn()` avec le même préfixe `  [OK]`, `  [FAIL]`, `  [WARN]` pour que `run_tests.py` puisse compter les résultats. Le fichier doit afficher un résumé final au format `OK: X | WARN: Y | FAIL: Z | TOTAL: T`.

Une fois le fichier créé, ajouter le nom de la suite (ex: `"AGRO"`) dans la liste `ALL_SUITES` du fichier `run_tests.py` à la racine du projet.

---

## 10. Réutiliser le pipeline Sentinel-2 de Module 1

Tous les modules peuvent importer directement les composants de Module 1 sans les copier. Le fichier `ndbi_calculator.py` contient déjà les fonctions `calculate_ndvi()`, `calculate_bsi()`, `extract_change_regions()`, `apply_scl_mask()`, et `compute_confidence()` qui sont utiles pour tous les modules. Le fichier `sentinel_data_fetcher.py` gère automatiquement la priorité entre les sources (CDSE → Sentinel Hub → Planetary Computer → GEE).

Les images Sentinel-2 en base (`ImageSatellite`) sont partagées entre tous les modules. Il n'est pas nécessaire de ré-importer des images qui couvrent déjà la zone et les dates souhaitées.

---

## 11. Documentation de référence

| Document | À lire pour... |
|---|---|
| `README.md` | Vue d'ensemble, installation, toutes les commandes avec leurs options |
| `analyse_complet_1.F.md` | Audit technique exhaustif Module 1 (142 Ko) — tous les bugs connus, corrections appliquées, limitations documentées |
| `AUDIT FINAL MODULE 1.md` | Résumé non-technique du pipeline pour la présentation |
| `module1_urbanisme/pipeline/verification_4_couches.py` | Logique complète de classification rouge/orange/vert/veille |
| `module1_urbanisme/management/commands/run_detection.py` | Pipeline principal complet commenté (800 lignes) — référence pour créer M2/M3 |
