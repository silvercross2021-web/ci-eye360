# 📋 AUDIT COMPLET — CIV-Eye Module 1 Urbanisme (Treichville)
> **Date** : 02 Mars 2026 | **Auditeur** : Antigravity (Expert SIG/Architecte Logiciel)  
> **Fichier à lire avant tout déploiement terrain**

---

## 🌍 PARTIE 1 — CONTEXTE DU PROJET : CE QUE FAIT CIV-EYE MODULE 1

### En une phrase
CIV-Eye Module 1 est un **système de surveillance automatique des constructions** sur la commune de Treichville (Abidjan). Il compare deux images satellites prises à un an d'intervalle pour détecter les nouvelles constructions et vérifier si elles respectent le plan de zonage cadastral.

### Les données disponibles (dans `data_use/`)

| Fichier | Taille | Rôle |
|---|---|---|
| `Abidjan_33333010.geojsonl` | 233 MB | 658 664 empreintes de bâtiments existants (Microsoft ~2023-2024). Sert de **filtre de base** : si un bâtiment est déjà là, pas d'alerte. |
| `cadastre_treichville_v10 (1).geojson` | 19 KB | 19 zones cadastrales de Treichville avec leur statut : **forbidden** (interdit), **conditional** (sous conditions), **buildable** (constructible). |
| `sentinel/` | ~1.2 MB | 9 images Sentinel-2 : **T1 = 29 Jan 2024** (référence), **T2 = 13 Jan 2025** (détection). Bandes B04, B08, B11 pour les deux dates + B12 pour T2. |
| `T1.zip` / `T2.zip` | ~400-537 KB | Archives des images satellites (déjà extraites dans `sentinel/`). |

### Les images Sentinel disponibles exactement

```
📁 sentinel/
  T1 (Référence — Janvier 2024)
  ├── 2024-01-29-00-00_..._B04_(Raw).tiff   ← Rouge (Red)
  ├── 2024-01-29-00-00_..._B08_(Raw).tiff   ← NIR (Near Infrared)
  ├── 2024-01-29-00-00_..._B11_(Raw).tiff   ← SWIR1
  └── 2024-01-29-00-00_..._Scene_classification_map_.tiff

  T2 (Détection — Janvier 2025)
  ├── 2025-01-13-00-00_..._B04_(Raw).tiff
  ├── 2025-01-13-00-00_..._B08_(Raw).tiff
  ├── 2025-01-13-00-00_..._B11_(Raw).tiff
  ├── 2025-01-13-00-00_..._B12_(Raw).tiff  ← Uniquement T2
  └── 2025-01-13-00-00_..._Scene_classification_map_.tiff
```

> ⚠️ **T1 n'a pas de B12** — le code doit gérer cette asymétrie.

### Comment fonctionne le pipeline (logique voulue)

```
Images Sentinel T1 + T2
        ↓
   Calcul NDBI = (B11 - B08) / (B11 + B08)  pour T1 et T2
        ↓
   Calcul BSI = (B11 - B08) / (B11 + B08)  pour T2 (détection terrassement)
        ↓
   Détection changements : NDBI_T2 > 0.2 ET NDBI_T1 ≤ 0.2  → Nouvelle construction
                           BSI_T2 > 0.15 ET NDBI_T2 ≤ 0.2  → Terrassement
        ↓
   Pour chaque région détectée : ENTONNOIR 4 COUCHES
     Couche 1 : Ce bâtiment est-il dans Microsoft Footprints ? → OUI → Ignorer (déjà existant)
     Couche 2 : NDBI_T1 > 0.2 ? → OUI → Ignorer (existait déjà en 2024)
     Couche 3 : Le changement NDBI est-il cohérent ? → NON → Ignorer
     Couche 4 : Dans quelle zone cadastrale ? → Forbidden/Conditional/Buildable
        ↓
   Classification finale et stockage BDD
     🔴 infraction_zonage  (zone forbidden)
     🟠 sous_condition     (zone conditional)
     🟢 conforme           (zone buildable)
     🔵 surveillance_preventive (terrassement détecté)
```

### Architecture technique actuelle

- **Backend** : Django 5.2 + SQLite (⚠️ temporaire, plan prévoie PostgreSQL+PostGIS)
- **Frontend** : HTML + Bootstrap 5 + Leaflet.js (carte interactive)
- **Données géo** : stockées en texte GeoJSON dans des `TextField` (⚠️ pas de champs PostGIS)
- **Management commands** : `import_cadastre`, `import_sentinel`, `import_microsoft`, `run_detection`
- **API REST** : Django REST Framework à `/api/v1/`

---

## 🔴 PARTIE 2 — LISTE COMPLÈTE DES ERREURS

### CRITICITÉ DES ERREURS

| Code | Symbole | Signification |
|---|---|---|
| **BLQ** | 🔴 | Bloquant — le système ne fonctionnera pas du tout |
| **MAJ** | 🟠 | Majeur — résultats incorrects ou incomplets |
| **MIN** | 🟡 | Mineur — code non propre mais pas de crash |

---

## ═══ GROUPE A : PIPELINE CORE (LOGIQUE MÉTIER) ═══

---

### 🔴 ERREUR A1 [BLQ] — Couche 1 Microsoft = Hash MD5 aléatoire (ZERO requête spatiale)

**Fichier** : `pipeline/verification_4_couches.py` lignes 69–97

**Le problème concret** : La fonction qui doit vérifier "est-ce que ce bâtiment existe déjà dans la base Microsoft ?" ne fait **aucune vraie vérification**. Elle calcule un hash MD5 arbitraire et dit "oui présent" pour 10% des cas au hasard, puis tombe sur du code mort (`return False` jamais atteint).

```python
# ❌ CODE ACTUEL — CASSÉ
def _is_in_microsoft_footprints(self, geometry_geojson: str) -> bool:
    try:
        geometry_data = json.loads(geometry_geojson)
        if geometry_data.get('type') == 'Polygon' and geometry_data.get('coordinates'):
            coords = geometry_data['coordinates'][0]
            if coords:
                lon, lat = coords[0]  # ← extrait mais JAMAIS utilisé
                
            # ICI : l'indentation est cassée (import hashlib hors du bloc if)
        import hashlib   # ← ligne mal indentée, hors du if!
        geometry_hash = int(hashlib.md5(geometry_geojson.encode()).hexdigest()[:8], 16)
        return (geometry_hash % 10) == 0  # ← 10% aléatoire, résultat sans sens
        
        return False  # ← DEAD CODE, jamais atteint!
```

**Impact** : Faux positifs massifs. Des bâtiments construits avant 2024 seront signalés comme nouvelles constructions.

**✅ CORRECTIF A1** — Remplacer entièrement la méthode `_is_in_microsoft_footprints` :

```python
def _is_in_microsoft_footprints(self, geometry_geojson: str) -> bool:
    """
    Couche 1: Vérifie si la géométrie intersecte un bâtiment Microsoft existant.
    Utilise un test d'overlap de bounding-box (compatible SQLite).
    Migration vers ST_Intersects PostGIS recommandée pour la production.
    """
    try:
        geometry_data = json.loads(geometry_geojson)
        if geometry_data.get('type') != 'Polygon':
            return False
        
        coords = geometry_data['coordinates'][0]
        if not coords:
            return False
        
        # Calcul de la bounding box de la détection candidate
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        cand_min_lon, cand_max_lon = min(lons), max(lons)
        cand_min_lat, cand_max_lat = min(lats), max(lats)
        
        TOLERANCE = 0.0001  # ~10 mètres
        
        # Parcourir les footprints Microsoft chargés (Treichville uniquement)
        for footprint in MicrosoftFootprint.objects.all().iterator(chunk_size=500):
            try:
                fp_geom = json.loads(footprint.geometry_geojson)
                fp_coords = fp_geom.get('coordinates', [[]])[0]
                if not fp_coords:
                    continue
                fp_lons = [c[0] for c in fp_coords]
                fp_lats = [c[1] for c in fp_coords]
                fp_min_lon, fp_max_lon = min(fp_lons), max(fp_lons)
                fp_min_lat, fp_max_lat = min(fp_lats), max(fp_lats)
                
                # Test d'overlap AABB
                overlaps = (
                    cand_min_lon - TOLERANCE < fp_max_lon and
                    cand_max_lon + TOLERANCE > fp_min_lon and
                    cand_min_lat - TOLERANCE < fp_max_lat and
                    cand_max_lat + TOLERANCE > fp_min_lat
                )
                if overlaps:
                    self.logger.info(f"Bâtiment trouvé dans Microsoft Footprints — ignoré")
                    return True
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
        
        return False
        
    except Exception as e:
        self.logger.error(f"Erreur vérification Microsoft: {str(e)}")
        return False  # Si erreur, on laisse passer pour analyse (pas de filtrage abusif)
```

---

### 🔴 ERREUR A2 [BLQ] — Couche 4 Classification = Sélection de zone par hash aléatoire

**Fichier** : `pipeline/verification_4_couches.py` lignes 121–163

**Le problème** : La classification cadastrale choisit une zone **parmi les 19 cadastrales de manière aléatoire** basée sur un hash de la géométrie, au lieu de chercher quelle zone contient réellement le point.

```python
# ❌ CODE ACTUEL — Classification sans sens géographique
zones = ZoneCadastrale.objects.all()  # Charge TOUTES les 19 zones
zone_index = zone_hash % zones.count()
zone = zones[zone_index]  # ← Une zone prise au hasard parmi les 19!
```

**Impact** : Une construction dans le Port (forbidden→alerte rouge) peut être classée comme "conforme" (buildable). Les résultats sont complètement aléatoires.

**✅ CORRECTIF A2** — Remplacer `_classify_by_zoning` :

```python
def _classify_by_zoning(self, geometry_geojson: str,
                         change_type: str, bsi_val):
    """
    Couche 4: Classification par intersection spatiale réelle avec le cadastre.
    Utilise Shapely pour le test géométrique (compatible SQLite).
    """
    try:
        from shapely.geometry import shape
        
        candidate_geom = shape(json.loads(geometry_geojson))
        centroid = candidate_geom.centroid
        
        matched_zone = None
        best_overlap = 0
        
        for zone in ZoneCadastrale.objects.all():
            try:
                zone_geom = shape(json.loads(zone.geometry_geojson))
                # Test si le centroid de la détection est dans la zone
                if zone_geom.contains(centroid):
                    matched_zone = zone
                    break
                # Sinon tester l'intersection (cas polygone à cheval)
                if zone_geom.intersects(candidate_geom):
                    overlap = zone_geom.intersection(candidate_geom).area
                    if overlap > best_overlap:
                        best_overlap = overlap
                        matched_zone = zone
            except Exception:
                continue
        
        if not matched_zone:
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': 'Construction hors périmètre cadastral connu. Inspection recommandée.',
                'zone_id': None,
                'zone_name': 'Hors cadastre',
                'confidence': 0.5
            }
        
        if change_type == 'new_construction':
            return self._classify_new_construction(matched_zone)
        elif change_type == 'soil_activity':
            return self._classify_soil_activity(matched_zone)
        else:
            return self._classify_default(matched_zone)
            
    except ImportError:
        self.logger.error("Shapely non installé ! pip install shapely>=2.0")
        raise RuntimeError("Shapely requis pour la classification spatiale.")
    except Exception as e:
        self.logger.error(f"Erreur classification: {str(e)}")
        return {
            'status': 'sous_condition', 'alert_level': 'orange',
            'message': 'Erreur classification — inspection requise', 'confidence': 0.3
        }
```

---

### 🔴 ERREUR A3 [BLQ] — `alert_level = 'surveillance_preventive'` invalide (crash BDD garanti)

**Fichier** : `pipeline/verification_4_couches.py` ligne 235

```python
# ❌ BUG
return {
    'status': 'surveillance_preventive',
    'alert_level': 'surveillance_preventive',  # ← INVALIDE!
    ...
}
```

Le modèle `DetectionConstruction` définit `ALERT_LEVEL_CHOICES` avec `'veille'` et pas `'surveillance_preventive'`. Django rejettera l'enregistrement (erreur de validation ou colonne invalide).

**✅ CORRECTIF A3** — Dans `_classify_soil_activity` ligne 235 :

```python
return {
    'status': 'surveillance_preventive',
    'alert_level': 'veille',   # ← Correct selon ALERT_LEVEL_CHOICES
    'message': f"Terrassement détecté ({zone.name} - {zone_status}). "
              f"Surveillance activée pour analyse T3.",
    'zone_id': zone.zone_id,
    'zone_name': zone.name,
    'zone_type': zone.zone_type,
    'confidence': 0.6
}
```

---

### 🔴 ERREUR A4 [BLQ] — BSI utilise B04 au lieu de B08 (formule incorrecte)

**Fichier** : `pipeline/ndbi_calculator.py` lignes 93–96

Le plan v2.0 spécifie BSI_approx = `(B11 - B08) / (B11 + B08)`.
L'implémentation calcule `(B11 - B04) / (B11 + B04)` — ce qui est différent physiquement.

```python
# ❌ CODE ACTUEL
bsi = np.where(
    (swir_data + red_data) == 0,
    0,
    (swir_data - red_data) / (swir_data + red_data)  # ← (B11 - B04)/(B11 + B04)
)
```

**✅ CORRECTIF A4** — Dans `calculate_bsi`, utiliser `nir_data` (B08) au lieu de `red_data` (B04) :

```python
# ✅ CORRECTION dans calculate_bsi(), remplacer le bloc de calcul :
with np.errstate(divide='ignore', invalid='ignore'):
    bsi = np.where(
        (swir_data + nir_data) == 0,   # ← nir_data = B08
        0,
        (swir_data - nir_data) / (swir_data + nir_data)  # ← (B11 - B08)/(B11 + B08)
    )
# Note: b04_path est conservé en signature pour compatibilité mais n'est plus utilisé ici
```

---

### 🔴 ERREUR A5 [BLQ] — `detect_construction_changes()` : Chemins de bandes construits de façon cassée

**Fichier** : `pipeline/ndbi_calculator.py` lignes 274–299

Cette fonction utilitaire (utilisée en fallback) construit les chemins de fichiers par remplacement de chaînes fragile :

```python
# ❌ CODE ACTUEL — si le chemin ne contient pas '_B04_', replace() ne fait rien
ndbi_t1_path.replace('_B04_', '_B08_').replace('_B11_', '_B08_')
# → Même fichier passé deux fois → NDBI = 0 partout → aucune détection
```

**✅ CORRECTIF A5** — Refactoriser avec des paramètres explicites :

```python
def detect_construction_changes(b08_t1_path: str, b11_t1_path: str,
                                 b08_t2_path: str, b11_t2_path: str,
                                 b04_t2_path: str = None,
                                 b08_bsi_path: str = None,
                                 b11_bsi_path: str = None) -> Dict:
    """Pipeline de détection avec chemins explicites par bande."""
    calculator = NDBICalculator()
    ndbi_t1 = calculator.calculate_ndbi(b08_t1_path, b11_t1_path)
    ndbi_t2 = calculator.calculate_ndbi(b08_t2_path, b11_t2_path)
    bsi_t2 = None
    if b08_bsi_path and b11_bsi_path:
        bsi_t2 = calculator.calculate_bsi(b04_t2_path, b08_bsi_path, b11_bsi_path)
    return calculator.detect_changes(ndbi_t1, ndbi_t2, bsi_t2)
```

---

### 🔴 ERREUR A6 [BLQ] — `run_detection.py` : Géométries en coordonnées pixels, pas en WGS84

**Fichier** : `management/commands/run_detection.py` lignes 193–213

La méthode `create_mock_geometry()` crée des polygones à partir des coordonnées **pixels du raster** (lignes/colonnes), pas en longitude/latitude WGS84. Résultat : des coordonnées comme `[10, 5]` au lieu de `[-4.01, 5.30]`.

```python
# ❌ CODE ACTUEL — coordonnées pixel, pas géographiques
geometry = {
    "type": "Polygon",
    "coordinates": [[
        [centroid[1] - size/1000, centroid[0] - size/1000],  # ← col, row = pixel!
        ...
    ]]
}
```

**Impact** : Toutes les détections seront géolocalisées en dehors de Treichville → classification cadastrale toujours "hors cadastre" → 100% classées `sous_condition` par défaut.

**✅ CORRECTIF A6** — Transformer les coordonnées pixel → WGS84 via le transform rasterio :

```python
def pixel_to_geo(self, row, col, raster_transform):
    """Convertit des coordonnées pixel en lon/lat WGS84."""
    import rasterio.transform as rt
    lon, lat = rt.xy(raster_transform, row, col)
    return lon, lat

def create_real_geometry(self, region, raster_transform, pixel_size_degrees=0.00009):
    """
    Crée un polygone GeoJSON en WGS84 à partir d'une région raster.
    pixel_size_degrees ≈ 10m en degrés à la latitude d'Abidjan.
    """
    centroid_row, centroid_col = region['centroid']
    lon, lat = self.pixel_to_geo(centroid_row, centroid_col, raster_transform)
    
    # Surface approximative basée sur la taille de la région
    size = max(region['size_pixels'], 1) * pixel_size_degrees
    half = size / 2
    
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half]
        ]]
    }
    return json.dumps(geometry)
```

Et dans `calculate_ndbi_pipeline`, retourner aussi le `transform` du raster T2 :

```python
# Ajouter dans calculate_ndbi_pipeline :
with rasterio.open(bands_t2['B08']) as src:
    raster_transform = src.transform
return {
    'ndbi_t1': ndbi_t1, 'ndbi_t2': ndbi_t2, 'bsi_t2': bsi_t2,
    'changes': change_results,
    'raster_transform': raster_transform  # ← NOUVEAU
}
```

---

### 🟠 ERREUR A7 [MAJ] — Filtrage BBOX Microsoft : 1 seul point au lieu de l'enveloppe complète

**Fichier** : `management/commands/import_microsoft.py` ligne 120  
et `pipeline/import_microsoft_footprints.py` ligne 156

```python
# ❌ CODE ACTUEL — test sur le PREMIER point seulement
lon, lat = coords[0]
return (bbox['min_lon'] <= lon <= bbox['max_lon'] and ...)
```

Un bâtiment à cheval sur la limite de Treichville peut être raté si son premier sommmet est hors BBOX.

**✅ CORRECTIF A7** — Dans les **deux** fichiers, remplacer `is_in_bbox` :

```python
def is_in_bbox(self, feature, bbox):
    """Vérifie si le polygone intersecte la bounding box (enveloppe complète)."""
    geometry = feature.get('geometry', {})
    coordinates = geometry.get('coordinates', [])
    if not coordinates or geometry.get('type') != 'Polygon':
        return False
    
    all_coords = coordinates[0]
    if not all_coords:
        return False
    
    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    
    poly_min_lon, poly_max_lon = min(lons), max(lons)
    poly_min_lat, poly_max_lat = min(lats), max(lats)
    
    # Chevauchement (même partiel)
    return not (
        poly_max_lon < bbox['min_lon'] or
        poly_min_lon > bbox['max_lon'] or
        poly_max_lat < bbox['min_lat'] or
        poly_min_lat > bbox['max_lat']
    )
```

---

### 🟠 ERREUR A8 [MAJ] — Import Sentinel : chemins relatifs non résolus (FileNotFoundError probable)

**Fichier** : `management/commands/import_sentinel.py` lignes 148–152

```python
# ❌ CODE ACTUEL — chemin relatif non résolu
base_path = 'module1_urbanisme/data_use/sentinel'
band_paths = {band: os.path.join(base_path, filename) ...}
```

Si la commande est exécutée depuis un répertoire différent de `SIADE_hackathon/`, les chemins seront introuvables lors du calcul NDBI.

**✅ CORRECTIF A8** — Utiliser un chemin absolu :

```python
from django.conf import settings

base_path = os.path.join(settings.BASE_DIR, 'module1_urbanisme', 'data_use', 'sentinel')
band_paths = {
    band: os.path.join(base_path, filename)
    for band, filename in bands.items()
}
```

---

### 🟠 ERREUR A9 [MAJ] — `import_cadastre.py` : `models.Count` non importé

**Fichier** : `pipeline/import_cadastre.py` ligne 134

```python
# ❌ CODE ACTUEL — models non importé dans ce fichier
stats = ZoneCadastrale.objects.values('buildable_status').annotate(count=models.Count('id'))
# → NameError: name 'models' is not defined
```

**✅ CORRECTIF A9** :

```python
# En haut du fichier, remplacer :
from django.db.models import Count

# Et ligne 134 :
stats = ZoneCadastrale.objects.values('buildable_status').annotate(count=Count('id'))
```

> ⚠️ Ce bug existe dans **les deux** fichiers `import_cadastre.py` : dans `pipeline/` ET dans `management/commands/`.

---

### 🟠 ERREUR A10 [MAJ] — Dashboard : Compteur "Inspections Requises" pointe vers le mauvais status

**Fichier** : `views_web.py` lignes 24–29

```python
# ❌ CODE ACTUEL — surveillance compte 'surveillance_preventive' mais le badge dit "Orange/Inspection"
detections_surveillance=Count('id', filter=Q(status='surveillance_preventive')),
```

Le badge "Alerte Orange" (Inspections Requises) devrait compter `sous_condition`, pas `surveillance_preventive`.

**✅ CORRECTIF A10** — Dans `views_web.py` ET `views.py` :

```python
detections_stats = DetectionConstruction.objects.aggregate(
    total_detections=Count('id'),
    detections_infraction=Count('id', filter=Q(status='infraction_zonage')),
    detections_sous_condition=Count('id', filter=Q(status='sous_condition')),   # ← renommé
    detections_conforme=Count('id', filter=Q(status='conforme')),
    detections_preventive=Count('id', filter=Q(status='surveillance_preventive'))
)
```

Et dans `dashboard.html` ligne 33 :
```html
<h3 class="card-title">{{ detections_stats.detections_sous_condition }}</h3>
```

---

## ═══ GROUPE B : IMPORT & DONNÉES ═══

---

### 🟠 ERREUR B1 [MAJ] — `import_microsoft.py` commande : `bulk_create` absent → très lent

**Fichier** : `management/commands/import_microsoft.py` ligne 72

```python
# ❌ CODE ACTUEL — un INSERT par bâtiment = catastrophiquement lent
MicrosoftFootprint.objects.create(**footprint_data)
```

Pour des milliers de bâtiments, un INSERT par ligne est ingérable.

**✅ CORRECTIF B1** — Utiliser `bulk_create` :

```python
def handle(self, *args, **options):
    # ... (paramètres identiques)
    chunk = []
    CHUNK_SIZE = 500
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            try:
                feature = json.loads(line.strip())
                if self.is_in_bbox(feature, bbox):
                    footprint_data = self.parse_feature(feature)
                    chunk.append(MicrosoftFootprint(**footprint_data))
                    imported_count += 1
                    
                    if len(chunk) >= CHUNK_SIZE:
                        with transaction.atomic():
                            MicrosoftFootprint.objects.bulk_create(chunk, batch_size=500)
                        chunk = []
                else:
                    skipped_count += 1
            except Exception as e:
                skipped_count += 1
                
    # Dernier chunk
    if chunk:
        with transaction.atomic():
            MicrosoftFootprint.objects.bulk_create(chunk, batch_size=500)
```

---

### 🟡 ERREUR B2 [MIN] — `import_sentinel.py` : T1 n'a pas de B12 → KeyError possible

**Fichier** : `management/commands/import_sentinel.py` lignes 141–145

La vérification des bandes requises (`required_bands = ['B04', 'B08', 'B11']`) est correcte. Mais le code stocke `B12` dans `band_paths` pour T2 sans problème. Aucun crash si B12 absent → OK. Juste à documenter.

---

### 🟡 ERREUR B3 [MIN] — `import_microsoft_footprints.py` (pipeline/) : `pbar.update(len(chunk))` mort

**Fichier** : `pipeline/import_microsoft_footprints.py` ligne 98

```python
chunk = []              # Reset du chunk
pbar.update(len(chunk)) # ← len([]) = 0 toujours!
```

La barre de progression reste à 0 après chaque chunk importé. Cosmétique, pas de crash.

---

## ═══ GROUPE C : HTML / FRONTEND ═══

---

### 🟠 ERREUR C1 [MAJ] — Disclaimer juridique absent des alertes rouges

**Fichier** : `templates/module1/detection_detail.html`

Le plan v2.0 exige un disclaimer : *"Ce diagnostic ne constitue pas une qualification juridique"*. Il est totalement absent de la page de détail.

**✅ CORRECTIF C1** — Ajouter dans `detection_detail.html` après la section "Conformité au zonage" (après ligne 226) :

```html
{% if detection.alert_level == 'rouge' or detection.alert_level == 'orange' %}
<div class="alert alert-warning border-2 border-warning mt-3" role="alert">
    <div class="d-flex align-items-start gap-2">
        <i class="fas fa-balance-scale fa-lg text-warning mt-1"></i>
        <div>
            <strong>⚠️ Avertissement Juridique Obligatoire</strong>
            <p class="mb-0 small mt-1">
                Ce diagnostic est produit automatiquement à partir du Plan de Zonage 
                Urbanistique V10 de Treichville et d'images satellite Sentinel-2. 
                Il <strong>ne constitue pas une qualification juridique</strong> d'infraction 
                urbanistique. La vérification terrain et la décision formelle relèvent 
                exclusivement de l'agent cadastral habilité.
            </p>
        </div>
    </div>
</div>
{% endif %}
```

---

### 🟠 ERREUR C2 [MAJ] — Bouton "Traiter" est une popup vide (feedback terrain cassé)

**Fichier** : `templates/module1/detection_detail.html` lignes 300–302

```javascript
// ❌ CODE ACTUEL — ne fait rien de utile
function markForVerification() {
    alert('Fonctionnalité à implémenter: Marquer comme vérifié');
}
```

L'API backend `/api/v1/detections/{id}/traiter/` est correctement implémentée mais le frontend ne l'appelle jamais.

**✅ CORRECTIF C2** — Remplacer le bloc `<div class="d-grid gap-2">` dans `detection_detail.html` et le script `markForVerification()` :

```html
<!-- Dans la section Actions, remplacer le bouton existant -->
{% if detection.statut_traitement == 'en_attente' or detection.statut_traitement == 'en_investigation' %}
<div class="card mt-3">
    <div class="card-header">
        <h6 class="mb-0"><i class="fas fa-clipboard-check"></i> Traitement Agent Terrain</h6>
    </div>
    <div class="card-body">
        <div class="mb-3">
            <label class="form-label">Commentaire terrain *</label>
            <textarea id="input-commentaire" class="form-control" rows="3" 
                      placeholder="Décrivez votre observation terrain..."></textarea>
        </div>
        <div class="d-grid gap-2">
            <button class="btn btn-success" onclick="traiterDetection('confirme')">
                <i class="fas fa-check-circle"></i> Confirmer l'infraction
            </button>
            <button class="btn btn-warning" onclick="traiterDetection('en_investigation')">
                <i class="fas fa-search"></i> Mettre en investigation
            </button>
            <button class="btn btn-outline-secondary" onclick="traiterDetection('faux_positif')">
                <i class="fas fa-times-circle"></i> Marquer comme Faux Positif
            </button>
        </div>
    </div>
</div>
{% else %}
<div class="alert alert-success">
    <i class="fas fa-check"></i> 
    <strong>Traité</strong> : {{ detection.get_statut_traitement_display }}
    {% if detection.date_traitement %}
    <br><small>Le {{ detection.date_traitement|date:"d/m/Y à H:i" }}</small>
    {% endif %}
</div>
{% endif %}
```

Et dans le bloc `{% block extra_js %}`, ajouter :

```javascript
async function traiterDetection(nouveauStatut) {
    const commentaire = document.getElementById('input-commentaire')?.value?.trim() || '';
    
    if (['confirme', 'faux_positif'].includes(nouveauStatut) && !commentaire) {
        alert('Un commentaire est obligatoire pour confirmer ou marquer comme faux positif.');
        return;
    }
    
    const csrfToken = document.cookie
        .split('; ')
        .find(r => r.startsWith('csrftoken='))
        ?.split('=')[1];
    
    try {
        const response = await fetch(`/api/v1/detections/${detectionData.id}/traiter/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                statut_traitement: nouveauStatut,
                commentaire_terrain: commentaire
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            // Recharger la page pour refléter le nouveau statut
            window.location.reload();
        } else {
            alert('Erreur : ' + JSON.stringify(data));
        }
    } catch (e) {
        alert('Erreur réseau : ' + e.message);
    }
}
```

---

### 🟡 ERREUR C3 [MIN] — Carte Leaflet : détections affichées comme Points, pas Polygones

**Fichier** : `templates/module1/dashboard.html` lignes 244–268

La geometrie stockée est un `Polygon` (type GeoJSON). Mais le code Leaflet utilise `pointToLayer` (pour des `Point`), ce qui ignore les polygones.

```javascript
// ❌ CODE ACTUEL — pointToLayer ne s'applique qu'aux Point GeoJSON
detectionsLayer = L.geoJSON(data, {
    pointToLayer: function(feature, latlng) { ... }  // ignoré pour Polygon!
});
```

**✅ CORRECTIF C3** — Utiliser `style` au lieu de `pointToLayer` pour les polygones :

```javascript
detectionsLayer = L.geoJSON(data, {
    style: function(feature) {
        const colors = {
            'rouge': '#dc3545', 'orange': '#fd7e14',
            'vert': '#198754', 'veille': '#0dcaf0'
        };
        const color = colors[feature.properties.alert_level] || '#888888';
        return {
            fillColor: color, color: '#fff',
            weight: 2, opacity: 0.9, fillOpacity: 0.7
        };
    },
    onEachFeature: function(feature, layer) {
        layer.bindPopup(`
            <strong>Détection #${feature.properties.id}</strong><br>
            ${feature.properties.alert_label}<br>
            ${feature.properties.zone_name || 'Hors cadastre'}<br>
            <small>NDBI: ${(feature.properties.ndbi_t1 ?? 0).toFixed(2)} → 
                         ${(feature.properties.ndbi_t2 ?? 0).toFixed(2)}</small><br>
            <a href="/detections/${feature.properties.id}/" class="btn btn-sm btn-primary mt-1">
                Voir détails
            </a>
        `);
    }
}).addTo(map);
```

---

### 🟡 ERREUR C4 [MIN] — `detections_list.html` : titre redondant ("Détections détectées")

**Fichier** : `templates/module1/detections_list.html` ligne 75

```html
<!-- ❌ Redondance -->
<h5 class="mb-0">Détections détectées</h5>
```

**✅ CORRECTIF** : `<h5 class="mb-0">Liste des Constructions Détectées</h5>`

---

### 🟡 ERREUR C5 [MIN] — Barre de progression `data-width` appliquée mais en doublon

**Fichier** : `templates/module1/dashboard.html` L.110 et `detections_list.html` L.139

Les barres de progression utilisent à la fois `style="width: X%"` via `{% widthratio %}` ET `data-width` appliqué par JavaScript. L'attribut `data-width` est inutile quand `style` est déjà défini en inline. Pas de crash.

---

## ═══ GROUPE D : CONFIGURATION & ARCHITECTURE ═══

---

### 🟠 ERREUR D1 [MAJ] — SQLite au lieu de PostgreSQL+PostGIS

**Fichier** : `config/settings.py` lignes 80–85

```python
# ❌ CONFIG ACTUELLE
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", ...}}
```

SQLite est utilisé car GDAL/PostGIS ne sont pas installés sur Windows. Pour le hackathon c'est acceptable, mais pour la production réelle sur terrain c'est **obligatoirement** à migrer.

> **Pour le hackathon** : Garder SQLite, c'est fonctionnel pour les démos.  
> **Pour la production** : Migrer vers PostgreSQL + PostGIS + `ST_Intersects` avec index GiST.

---

### 🟡 ERREUR D2 [MIN] — `settings.py` : `TEMPLATES` défini deux fois

**Fichier** : `config/settings.py` lignes 59–72 et 144–158

La configuration `TEMPLATES` est définie deux fois. Django utilise la **dernière** définition, ce qui écrase la première (qui n'avait pas le dossier `templates/`). Ça fonctionne par chance.

**✅ CORRECTIF** : Supprimer le premier bloc TEMPLATES (lignes 59–72) et ne garder que le second (avec `'DIRS': [BASE_DIR / 'templates']`).

---

### 🟡 ERREUR D3 [MIN] — `urls.py` : 3 `include('')` avec le même préfixe vide → conflits potentiels

**Fichier** : `config/urls.py` lignes 26–30

```python
path("", include('module1_urbanisme.urls_web')),
path("", include('module1_urbanisme.urls')),        # → /api/v1/...
path("", include('module1_urbanisme.urls_simple')), # → /api/v2/...
```

Django résout les URLs dans l'ordre. Si une URL correspond dans `urls_web`, elle ne sera jamais testée dans `urls`. C'est fragile. Pas de crash actuel car les préfixes (`api/v1/`, `api/v2/`) sont distincts.

---

### 🟡 ERREUR D4 [MIN] — Celery non implémenté (non bloquant pour hackathon)

Le plan v2.0 prévoit des tâches Celery pour le traitement asynchrone. Non implémenté, mais pour un hackathon avec des petites images Sentinel (~130KB chacune), le traitement synchrone est suffisant. À implémenter pour la production.

---

## 📊 RÉSUMÉ DES ERREURS

| Code | Sévérité | Description | Fichier principal |
|---|---|---|---|
| A1 | 🔴 BLQ | Couche 1 Microsoft = hash aléatoire | `pipeline/verification_4_couches.py` |
| A2 | 🔴 BLQ | Couche 4 Classification = zone aléatoire | `pipeline/verification_4_couches.py` |
| A3 | 🔴 BLQ | `alert_level='surveillance_preventive'` invalide | `pipeline/verification_4_couches.py` |
| A4 | 🔴 BLQ | BSI formule (B11-B04) ≠ (B11-B08) du plan | `pipeline/ndbi_calculator.py` |
| A5 | 🔴 BLQ | Chemins bandes construits de façon fragile | `pipeline/ndbi_calculator.py` |
| A6 | 🔴 BLQ | Géométries en coordonnées pixel, pas WGS84 | `management/commands/run_detection.py` |
| A7 | 🟠 MAJ | Filtrage BBOX par 1 point seulement | `import_microsoft.py` (×2 fichiers) |
| A8 | 🟠 MAJ | Chemins Sentinel relatifs → FileNotFoundError | `management/commands/import_sentinel.py` |
| A9 | 🟠 MAJ | `models.Count` non importé → NameError | `import_cadastre.py` (×2 fichiers) |
| A10 | 🟠 MAJ | Compteur Orange Dashboard (mauvais status) | `views_web.py` + `dashboard.html` |
| B1 | 🟠 MAJ | INSERT un par un au lieu de bulk_create | `management/commands/import_microsoft.py` |
| B2 | 🟡 MIN | B12 absent en T1 (documenté, non bloquant) | `import_sentinel.py` |
| B3 | 🟡 MIN | `pbar.update(0)` mort (cosmétique) | `pipeline/import_microsoft_footprints.py` |
| C1 | 🟠 MAJ | Disclaimer juridique absent alertes rouges | `templates/module1/detection_detail.html` |
| C2 | 🟠 MAJ | Bouton "Traiter" non câblé à l'API | `templates/module1/detection_detail.html` |
| C3 | 🟡 MIN | Leaflet `pointToLayer` ignoré pour Polygones | `templates/module1/dashboard.html` |
| C4 | 🟡 MIN | "Détections détectées" (titre redondant) | `templates/module1/detections_list.html` |
| C5 | 🟡 MIN | `data-width` doublon avec style inline | Multiple HTML |
| D1 | 🟠 MAJ | SQLite ≠ PostGIS (production uniquement) | `config/settings.py` |
| D2 | 🟡 MIN | `TEMPLATES` défini deux fois | `config/settings.py` |
| D3 | 🟡 MIN | 3 `include('')` avec préfixe vide | `config/urls.py` |
| D4 | 🟡 MIN | Celery non implémenté | *(absent)* |

---

## 🛠️ PARTIE 3 — ORDRE DE CORRECTIONS RECOMMANDÉ

> **Pour valider le pipeline avec les vraies données Sentinel, corrigez dans cet ordre :**

```
ÉTAPE 1 (30 min) — Corrections rapides sans refonte architecturale
  ✦ A3 : alert_level = 'veille'                    (1 ligne)
  ✦ A4 : BSI formule nir_data au lieu de red_data  (2 lignes)
  ✦ A9 : import Count dans import_cadastre.py      (1 ligne ×2)
  ✦ A10: detections_sous_condition dans views       (2 fichiers)

ÉTAPE 2 (1-2h) — Corrections spatiales fondamentales (bloquantes)
  ✦ A1 : Réécrire _is_in_microsoft_footprints()    (AABB réel)
  ✦ A2 : Réécrire _classify_by_zoning()             (Shapely)
  ✦ A7 : Corriger is_in_bbox() dans import_microsoft (×2 fichiers)

ÉTAPE 3 (1-2h) — Corrections pipeline de détection
  ✦ A6 : Transformer coordonnées pixel → WGS84 dans run_detection.py
  ✦ A8 : Chemins absolus dans import_sentinel.py
  ✦ A5 : Refactoriser detect_construction_changes()

ÉTAPE 4 (1h) — Corrections HTML/UI
  ✦ C1 : Ajouter disclaimer juridique
  ✦ C2 : Câbler le bouton "Traiter" à l'API
  ✦ C3 : Corriger Leaflet pour Polygones
```

---

## 🧪 PARTIE 4 — GUIDE DE TEST AVEC LES VRAIES DONNÉES

### Prérequis

```bash
# Installer les dépendances Python nécessaires (Windows)
pip install django djangorestframework
pip install rasterio numpy scipy shapely
pip install tqdm

# Vérifier que rasterio peut lire les TIFF
python -c "import rasterio; print(rasterio.__version__)"
python -c "from shapely.geometry import shape; print('Shapely OK')"
```

### Test 1 — Vérifier que les images Sentinel se lisent correctement

```bash
# Créer ce script : test_sentinel.py à la racine du projet
python test_sentinel.py
```

```python
# test_sentinel.py
import rasterio
import numpy as np

T1_B08 = 'module1_urbanisme/data_use/sentinel/2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B08_(Raw).tiff'
T1_B11 = 'module1_urbanisme/data_use/sentinel/2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B11_(Raw).tiff'
T2_B08 = 'module1_urbanisme/data_use/sentinel/2025-01-13-00-00_2025-01-13-23-59_Sentinel-2_L2A_B08_(Raw).tiff'
T2_B11 = 'module1_urbanisme/data_use/sentinel/2025-01-13-00-00_2025-01-13-23-59_Sentinel-2_L2A_B11_(Raw).tiff'

for path, label in [(T1_B08, 'T1 B08'), (T1_B11, 'T1 B11'), (T2_B08, 'T2 B08'), (T2_B11, 'T2 B11')]:
    with rasterio.open(path) as src:
        data = src.read(1).astype(float)
        print(f"\n{label}:")
        print(f"  CRS: {src.crs}")
        print(f"  Transform: {src.transform}")
        print(f"  Shape: {data.shape}")
        print(f"  Bounds: {src.bounds}")
        print(f"  Values — Min: {data.min():.1f}, Max: {data.max():.1f}, Mean: {data.mean():.1f}")

print("\n✅ Lecture Sentinel OK!")
```

**Résultat attendu** : CRS = EPSG:32630 ou 4326, Bounds dans les coordonnées d'Abidjan.

---

### Test 2 — Tester le calcul NDBI

```bash
# Depuis la racine SIADE_hackathon :
python -c "
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()
from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator

calc = NDBICalculator()
T1_B08 = 'module1_urbanisme/data_use/sentinel/2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B08_(Raw).tiff'
T1_B11 = 'module1_urbanisme/data_use/sentinel/2024-01-29-00-00_2024-01-29-23-59_Sentinel-2_L2A_B11_(Raw).tiff'
ndbi_t1 = calc.calculate_ndbi(T1_B08, T1_B11)

import numpy as np
print('NDBI T1 Stats:')
print(f'  Shape: {ndbi_t1.shape}')
print(f'  Min: {ndbi_t1.min():.3f}, Max: {ndbi_t1.max():.3f}')
print(f'  Pixels > 0.2 (surfaces baties): {np.sum(ndbi_t1 > 0.2)} / {ndbi_t1.size}')
print(f'  Taux surface batie T1: {100*np.mean(ndbi_t1 > 0.2):.1f}%')
print('✅ NDBI calculé correctement!')
"
```

---

### Test 3 — Import du cadastre

```bash
# Dans SIADE_hackathon/
python manage.py import_cadastre --dry-run
# Attendu : 19 zones affichées (7 forbidden, 3 conditional, 9 buildable)

python manage.py import_cadastre
# Vérifier :
python manage.py shell -c "
from module1_urbanisme.models import ZoneCadastrale
print(f'Zones importées: {ZoneCadastrale.objects.count()}')
for z in ZoneCadastrale.objects.all():
    print(f'  {z.zone_id} - {z.name} ({z.buildable_status})')
"
```

**Résultat attendu** : 19 zones avec leurs noms (Port, CARENA, zones résidentielles...).

---

### Test 4 — Import des images Sentinel

```bash
python manage.py import_sentinel --dry-run
# Attendu : 2 dates trouvées (2024-01-29 et 2025-01-13)

python manage.py import_sentinel
# Vérifier :
python manage.py shell -c "
from module1_urbanisme.models import ImageSatellite
for img in ImageSatellite.objects.all():
    print(f'{img.date_acquisition}: {list(img.bands.keys())}')
"
```

---

### Test 5 — Import Microsoft Footprints (limité pour test)

```bash
# Tester avec les 2000 premières lignes du fichier de 233MB
python manage.py import_microsoft --limit 2000 --dry-run
# Attendu : X empreintes dans bbox Treichville sur 2000 lignes

python manage.py import_microsoft --limit 2000
# Vérifier :
python manage.py shell -c "
from module1_urbanisme.models import MicrosoftFootprint
print(f'Empreintes importées: {MicrosoftFootprint.objects.count()}')
"
```

> ⚠️ Le fichier complet fait 233MB / 658 664 features. Utiliser `--limit` pour les tests. Pour un import complet en prod, utiliser `--limit 0` (sans limite) et attendre ~10-15 minutes.

---

### Test 6 — Pipeline de détection complet (DRY-RUN)

```bash
# Après avoir appliqué les correctifs A1 à A6 :
python manage.py run_detection --dry-run
# Attendu : Affichage du nombre de régions détectées sans écriture BDD

# Puis avec écriture :
python manage.py run_detection --date-t1 2024-01-29 --date-t2 2025-01-13
```

---

### Test 7 — Valider les résultats visuellement

```bash
# Démarrer le serveur de développement
python manage.py runserver

# Ouvrir dans le navigateur :
# http://127.0.0.1:8000/          → Dashboard avec carte
# http://127.0.0.1:8000/detections/ → Liste des détections
# http://127.0.0.1:8000/zones/     → Zones cadastrales

# Vérifier via l'API :
# http://127.0.0.1:8000/api/zones-geojson/    → Doit retourner 19 zones
# http://127.0.0.1:8000/api/detections-geojson/ → Doit retourner les détections
# http://127.0.0.1:8000/api/v1/detections/?status=infraction_zonage → Alertes rouges
```

---

### Test 8 — Vérification des résultats attendus

Après un pipeline complet sur Treichville avec les données réelles, vous devriez observer :

| Métrique | Valeur attendue | Commentaire |
|---|---|---|
| Zones cadastrales | 19 | 7 forbidden, 3 conditional, 9 buildable |
| Empreintes Microsoft | Quelques centaines à milliers | Après filtrage BBOX Treichville |
| Images Sentinel | 2 | T1=2024-01-29, T2=2025-01-13 |
| Nouvelles constructions détectées | Quelques dizaines | Dépend des seuils NDBI |
| Alertes rouges (infraction_zonage) | < 20% du total | Zones portuaires/industrielles |
| Alertes orange (sous_condition) | Variable | Zones conditional |
| Faux positifs | < 15% idéalement | Après calibration seuils |

---

### Script de validation automatique (post-pipeline)

```python
# validation_pipeline.py — à exécuter depuis la racine du projet
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()

from module1_urbanisme.models import ZoneCadastrale, MicrosoftFootprint, DetectionConstruction, ImageSatellite
from django.db.models import Count, Q

print("=" * 60)
print("RAPPORT DE VALIDATION — CIV-Eye Module 1")
print("=" * 60)

# 1. Données chargées
print(f"\n📊 DONNÉES IMPORTÉES:")
print(f"  Zones cadastrales    : {ZoneCadastrale.objects.count()} / 19 attendues")
print(f"  Empreintes Microsoft : {MicrosoftFootprint.objects.count()}")
print(f"  Images Sentinel      : {ImageSatellite.objects.count()} / 2 attendues")
print(f"  Détections créées    : {DetectionConstruction.objects.count()}")

# 2. Répartition statuts
print(f"\n🔔 RÉPARTITION DES ALERTES:")
for status, label in DetectionConstruction.STATUS_CHOICES:
    count = DetectionConstruction.objects.filter(status=status).count()
    print(f"  {label:<45}: {count}")

# 3. Vérification alert_level valides
invalid_alerts = DetectionConstruction.objects.exclude(
    alert_level__in=['rouge', 'orange', 'vert', 'veille']
).count()
print(f"\n✅ INTÉGRITÉ:")
print(f"  Alert_level invalides    : {invalid_alerts} (doit être 0)")
print(f"  Détections sans zone     : {DetectionConstruction.objects.filter(zone_cadastrale__isnull=True).count()}")
print(f"  Détections hors cadastre : attendu quelques-unes si bbox bord")

# 4. Zones cadastrales
print(f"\n🗺️ ZONES CADASTRALES:")
for bstatus, label in ZoneCadastrale.BUILDABLE_STATUS_CHOICES:
    count = ZoneCadastrale.objects.filter(buildable_status=bstatus).count()
    print(f"  {label:<25}: {count}")

print("\n" + "=" * 60)
```

---

## 📌 RÉSUMÉ EXÉCUTIF

| Phase | Tâche | Temps estimé |
|---|---|---|
| Corrections critiques (A1-A6) | Réécriture logique spatiale + formulas | 3-4h |
| Corrections majeures (A7-A10, B1) | Import + stats | 1h |
| Corrections HTML (C1-C3) | Disclaimer + bouton traiter + Leaflet | 1h |
| Import des données réelles | cadastre + sentinel + microsoft | 30min |
| Pipeline détection + validation | run_detection + vérification résultats | 1h |
| **TOTAL** | | **~7-8h de travail** |

> **Ce système, une fois corrigé, sera capable de détecter automatiquement les nouvelles constructions sur 100% de Treichville entre janvier 2024 et janvier 2025, de les classifier selon le plan de zonage V10, et de présenter les résultats aux agents cadastraux sur une interface cartographique interactive.**
