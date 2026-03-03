# FULL_DEVELOPMENT_PLAN_MODULE_1.md
## Plan de Développement Complet - Module 1 Urbanisme (CIV-Eye Treichville)

**Date**: 1er Mars 2026  
**Version**: v2.0  
**Auteur**: Expert Lead Developer Fullstack SIG/IA  

---

## 📋 ANALYSE DES DONNÉES EXISTANTES

### ✅ Données Disponibles

#### 1. Cadastre de Référence (Zonage)
- **Fichier**: `cadastre_treichville_v10 (1).geojson`
- **Status**: ✅ Validé et topologiquement parfait
- **Contenu**: 19 zones cadastrales (7 forbidden, 3 conditional, 9 buildable)
- **Métadonnées**: SRID 4326, bbox: [-4.03001, 5.28501, -3.97301, 5.32053]
- **Zones clés**: Port, CARENA, quartiers résidentiels, zones commerciales
- **⚠️ Rôle révisé v2**: Ce fichier définit des **règles de zonage** (usage des sols) et **non des droits individuels** (permis de construire). Il ne peut donc pas qualifier une construction d'illégale, mais il peut confirmer une **infraction urbanistique** dans les zones forbidden.

#### 2. Microsoft Building Footprints (Vérité Terrain T1)
- **Fichier**: `Abidjan_33333010.geojsonl` (233MB)
- **Format**: GeoJSON Lines (658,664 features)
- **Propriétés**: height (-1.0), confidence (-1.0)
- **Rôle**: Couche de vérité terrain représentant le bâti existant (~2023-2024). Tout bâtiment présent dans ce fichier est considéré comme **déjà existant avant le début de la surveillance** et ne déclenche pas d'alerte.
- **Limite à documenter**: La date exacte de production Microsoft n'est pas garantie. Un bâtiment construit entre la date Microsoft et T1 Sentinel peut être absent des deux. La combinaison "absent de Microsoft ET absent de T1 Sentinel" est le critère le plus robuste.

#### 3. Images Satellites Sentinel-2
- **Période T1**: Janvier 2024 (image de référence)
- **Période T2**: Janvier 2025 (image de détection)
- **Bandes disponibles**: B04 (Red), B08 (NIR), B11 (SWIR), B12 (SWIR2)
- **Classification**: Scene classification maps
- **Format**: TIFF géoréférencé

#### 4. Archives Complémentaires
- `T1.zip` et `T2.zip`: Données compressées à analyser
- `cadastre_treichville_v10 (1).html`: Visualisation web

---

## 🎯 OBJECTIFS TECHNIQUES MODULE 1

### Mission Principale (Révisée v2)
**Monitoring de Conformité Urbanistique** : Détecter automatiquement les nouvelles constructions apparues entre T1 et T2 dans la commune de Treichville, et les classifier selon leur conformité au plan de zonage cadastral V10.

> ⚠️ **Principe fondamental v2** : Le système ne déclare **jamais** qu'une construction est "illégale". Il détecte des **infractions au plan de zonage** (zone forbidden) ou des situations **nécessitant inspection** (zone conditional). La qualification juridique finale reste à l'agent cadastral humain.

### Fonctionnalités Clés
1. **Vérification en 4 couches** : Microsoft Footprints → Sentinel T1 → Sentinel T2 → Cadastre V10
2. **Calcul NDBI** à partir des bandes Sentinel-2 (B08/B11)
3. **Détection de nouvelles constructions** entre T1 (2024) et T2 (2025)
4. **Analyse de conformité au zonage** selon les 4 cas logiques
5. **Alertes graduées** (Rouge / Orange / Vert / Surveillance préventive)
6. **Dashboard de visualisation** cartographique

---

## 🏗️ ARCHITECTURE TECHNIQUE REQUISE

### Backend Django/Python
```python
# Stack technique
- Django 5.2+ (déjà configuré)
- Django REST Framework
- PostgreSQL + PostGIS (pour les données géospatiales)
- Celery + Redis (tâches asynchrones)
- GDAL/OGR (traitement géospatial)
- Rasterio (traitement images satellites)
- GeoPandas (analyse géospatiale)
- NumPy/SciPy (calculs NDBI + BSI)
```

### Frontend
```python
# Stack web
- HTML5/CSS3/JavaScript
- Leaflet.js ou Mapbox GL JS (cartographie)
- Bootstrap ou Tailwind CSS (UI)
- Chart.js (visualisations)
```

### Infrastructure
```python
# Services
- MinIO/AWS S3 (stockage images)
- Redis (cache + queue)
- Nginx (serveur web)
- Docker (containerisation)
```

---

## 📝 PLAN DE DÉVELOPPEMENT DÉTAILLÉ

### PHASE 1: CONFIGURATION BASE (Semaine 1)

#### 1.1 Configuration Django Apps
```bash
# Actions requises:
- Ajouter module1_urbanisme à INSTALLED_APPS
- Configurer PostgreSQL + PostGIS
- Installer dépendances Python
- Configurer media/static files
```

#### 1.2 Création Models Django (Révisés v2)
```python
class ZoneCadastrale(models.Model):
    zone_id = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    zone_type = models.CharField(max_length=50)  # harbour, residential, commercial, etc.
    buildable_status = models.CharField(max_length=20)  # forbidden, conditional, buildable
    geometry = models.PolygonField(srid=4326)
    metadata = models.JSONField(default=dict)


class ImageSatellite(models.Model):
    date_acquisition = models.DateField()
    satellite = models.CharField(max_length=50)
    bands = models.JSONField()  # B04, B08, B11, B12 paths
    classification_map = models.FileField()
    processed = models.BooleanField(default=False)


class MicrosoftFootprint(models.Model):
    """Bâtiments existants avant la période de surveillance (vérité terrain)."""
    geometry = models.PolygonField(srid=4326)
    source_file = models.CharField(max_length=100, default='Abidjan_33333010.geojsonl')
    date_reference = models.CharField(max_length=50, default='~2023-2024')


class DetectionConstruction(models.Model):
    """
    Représente une nouvelle construction détectée par le pipeline NDBI.

    STATUTS POSSIBLES (ne jamais utiliser 'illegal'):
    - infraction_zonage    : Zone forbidden. Infraction urbanistique confirmée par le zonage V10.
    - sous_condition       : Zone conditional. Inspection requise pour vérifier les servitudes.
    - conforme             : Zone buildable. Croissance urbaine normale, aucune alerte levée.
    - surveillance_preventive : NDBI élevé (terrassement) sans bâtiment formé visible. Mis en veille.
    """
    STATUS_CHOICES = [
        ('infraction_zonage', 'Infraction au Zonage'),
        ('sous_condition', 'Zone Sous Condition - Inspection Requise'),
        ('conforme', 'Développement Conforme'),
        ('surveillance_preventive', 'Surveillance Préventive - Terrassement Détecté'),
    ]

    ALERT_LEVEL_CHOICES = [
        ('rouge', 'Alerte Rouge'),
        ('orange', 'Alerte Orange'),
        ('vert', 'Notification Verte'),
        ('veille', 'Mise en Veille'),
    ]

    date_detection = models.DateTimeField(auto_now_add=True)
    zone_cadastrale = models.ForeignKey(ZoneCadastrale, on_delete=models.CASCADE, null=True)
    geometry = models.PolygonField(srid=4326)
    ndbi_t1 = models.FloatField(help_text="Valeur NDBI sur image T1 (référence)")
    ndbi_t2 = models.FloatField(help_text="Valeur NDBI sur image T2 (détection)")
    bsi_value = models.FloatField(null=True, blank=True, help_text="Bare Soil Index pour détection terrassement")
    surface_m2 = models.FloatField(null=True)
    confidence = models.FloatField()

    # Résultat de la vérification 4 couches
    present_in_microsoft = models.BooleanField(default=False)
    present_in_t1_sentinel = models.BooleanField(default=False)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    alert_level = models.CharField(max_length=10, choices=ALERT_LEVEL_CHOICES)
    verification_required = models.BooleanField(default=True)

    # Feedback agent terrain
    statut_traitement = models.CharField(
        max_length=20,
        choices=[('en_attente', 'En attente'), ('confirme', 'Confirmé'), ('faux_positif', 'Faux positif'), ('en_investigation', 'En investigation')],
        default='en_attente'
    )
    traitee_par = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    commentaire_terrain = models.TextField(blank=True)
```

#### 1.3 Migration Base de Données
```bash
python manage.py makemigrations module1_urbanisme
python manage.py migrate
```

---

### PHASE 2: INGESTION DONNÉES (Semaine 2)

#### 2.1 Import Cadastre
```python
# Pipeline d'import:
- Parser cadastre_treichville_v10.geojson
- Créer instances ZoneCadastrale
- Valider topologie (déjà validée v10)
- Indexer performances (GiST sur geometry)
```

#### 2.2 Import Images Sentinel
```python
# Pipeline d'import:
- Scanner dossier sentinel/
- Parser métadonnées TIFF
- Stocker chemins des bandes
- Créer instances ImageSatellite
- Valider alignement géographique
```

#### 2.3 Import Microsoft Building Footprints
```python
# Pipeline d'import:
- Parser Abidjan_33333010.geojsonl (658K features) en streaming (ligne par ligne)
- Filtrer zone géographique Treichville uniquement (bbox cadastre)
- Créer instances MicrosoftFootprint
- Créer index spatial GiST sur geometry
- Optimiser performances requêtes (ST_Intersects)

# Note de performance: Le fichier fait 233MB / 658K features.
# Utiliser GeoPandas chunking ou ogr2ogr pour l'import initial.
```

---

### PHASE 3: TRAITEMENT NDBI + BSI (Semaine 3)

#### 3.1 Calcul NDBI
```python
def calculate_ndbi(b08_path: str, b11_path: str) -> np.ndarray:
    """
    NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
    B08 = NIR (Near Infrared)
    B11 = SWIR1 (Short-wave Infrared)
    Valeurs positives => surfaces bâties ou sol nu réfléchissant.
    """
    with rasterio.open(b08_path) as nir_src, rasterio.open(b11_path) as swir_src:
        nir_data = nir_src.read(1).astype(float)
        swir_data = swir_src.read(1).astype(float)
        with np.errstate(divide='ignore', invalid='ignore'):
            ndbi = np.where(
                (swir_data + nir_data) == 0,
                0,
                (swir_data - nir_data) / (swir_data + nir_data)
            )
        return np.clip(ndbi, -1, 1)
```

#### 3.2 Calcul BSI (Bare Soil Index — pour cas "Sol Retourné")
```python
def calculate_bsi(b04_path: str, b08_path: str, b11_path: str, b12_path: str) -> np.ndarray:
    """
    BSI = ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))
    Détecte le sol nu / terrassement en cours.
    Complète le NDBI pour le cas 4 (surveillance préventive).
    Note: B02 non disponible → variante simplifiée avec B04 uniquement.
    BSI_approx = (B11 - B08) / (B11 + B08) (similaire à NDBI mais sensible aux sols nus)
    """
    with rasterio.open(b11_path) as swir_src, rasterio.open(b08_path) as nir_src:
        swir = swir_src.read(1).astype(float)
        nir = nir_src.read(1).astype(float)
        with np.errstate(divide='ignore', invalid='ignore'):
            bsi = np.where((swir + nir) == 0, 0, (swir - nir) / (swir + nir))
        return np.clip(bsi, -1, 1)
```

#### 3.3 Détection Changements
```python
def detect_new_constructions(
    ndbi_t1: np.ndarray,
    ndbi_t2: np.ndarray,
    bsi_t2: np.ndarray,
    threshold_built: float = 0.2,
    threshold_soil: float = 0.15
) -> dict:
    """
    Détecte deux types de changements:
    1. Nouvelle construction (bâtiment formé visible): NDBI_T2 > threshold ET NDBI_T1 <= threshold
    2. Terrassement en cours (sol retourné): BSI_T2 > threshold_soil ET NDBI_T2 < threshold_built
    """
    new_built = (ndbi_t2 > threshold_built) & (ndbi_t1 <= threshold_built)
    soil_activity = (bsi_t2 > threshold_soil) & (ndbi_t2 <= threshold_built)
    return {
        'new_constructions': new_built,
        'soil_activity': soil_activity
    }
```

---

### PHASE 4: VÉRIFICATION 4 COUCHES & CLASSIFICATION (Semaine 4)

#### 4.1 Pipeline de Vérification Complet
```python
def verify_detection(construction_geometry, ndbi_t1_val, ndbi_t2_val, bsi_val, change_type):
    """
    Entonnoir de vérification en 4 couches avant classification finale.

    Couche 1 — Microsoft Footprints (filtre de sécurité):
        Si le polygone intersecte un bâtiment Microsoft => déjà existant => ignorer.

    Couche 2 — Sentinel T1 (confirmation nouvelle construction):
        Si NDBI_T1 était déjà élevé => bâtiment existait en 2024 => ignorer.

    Couche 3 — Sentinel T2 (détection):
        Changement NDBI confirmé => nouvelle surface construite ou terrassement.

    Couche 4 — Cadastre V10 (classification):
        Application des 4 cas logiques selon zone.
    """

    # Couche 1: Vérification Microsoft
    present_microsoft = MicrosoftFootprint.objects.filter(
        geometry__intersects=construction_geometry
    ).exists()
    if present_microsoft:
        return None  # Bâtiment connu, ne pas alerter

    # Couche 2: Vérification T1 Sentinel
    if ndbi_t1_val > 0.2:
        return None  # Déjà bâti en T1

    # Couche 3: Confirmation changement (déjà validée en amont par detect_new_constructions)

    # Couche 4: Classification cadastrale
    return classify_by_zoning(construction_geometry, change_type, bsi_val)
```

#### 4.2 Classification par Zonage (Les 4 Cas Logiques)
```python
def classify_by_zoning(construction_geometry, change_type, bsi_val):
    """
    4 cas logiques de classification.
    Ne jamais utiliser le terme 'illégal' — uniquement 'infraction au zonage'.
    """

    zones = ZoneCadastrale.objects.filter(geometry__intersects=construction_geometry)

    if not zones.exists():
        # Zone hors cadastre = traiter comme zone sous condition par précaution
        return {
            'status': 'sous_condition',
            'alert_level': 'orange',
            'message': 'Construction hors périmètre cadastral connu. Inspection recommandée.'
        }

    zone = zones.first()  # Prendre la zone de plus grande intersection

    # CAS 1 — INFRACTION AU ZONAGE (Alerte Rouge)
    # La règle de zonage interdit toute construction ici, indépendamment de tout permis individuel.
    if zone.buildable_status == 'forbidden' and change_type == 'new_construction':
        return {
            'status': 'infraction_zonage',
            'alert_level': 'rouge',
            'message': f"Nouvelle construction détectée en Zone Interdite ({zone.name}). "
                       f"Le plan de zonage V10 interdit la construction dans cette zone. "
                       f"Transmission recommandée à l'agent cadastral pour vérification terrain."
        }

    # CAS 2 — CONSTRUCTION SOUS CONDITION (Alerte Orange)
    # Le zonage autorise sous réserve de servitudes. Inspection nécessaire.
    elif zone.buildable_status == 'conditional' and change_type == 'new_construction':
        return {
            'status': 'sous_condition',
            'alert_level': 'orange',
            'message': f"Nouvelle construction détectée en Zone Sous Condition ({zone.name}). "
                       f"Vérification du respect des servitudes de sécurité requise."
        }

    # CAS 3 — DÉVELOPPEMENT CONFORME (Notification Verte)
    # Zone constructible. Croissance normale enregistrée sans alerte d'infraction.
    elif zone.buildable_status == 'buildable' and change_type == 'new_construction':
        return {
            'status': 'conforme',
            'alert_level': 'vert',
            'message': f"Nouvelle construction en Zone Constructible ({zone.name}). "
                       f"Développement urbain conforme au zonage. Enregistrement sans alerte."
        }

    # CAS 4 — SOL RETOURNÉ / SURVEILLANCE PRÉVENTIVE (Mise en Veille)
    # Terrassement détecté (BSI élevé, NDBI bas) sans bâtiment encore formé.
    # Mis en veille pour surveillance lors de l'analyse T3.
    elif change_type == 'soil_activity':
        return {
            'status': 'surveillance_preventive',
            'alert_level': 'veille',
            'zone_status': zone.buildable_status,
            'message': f"Terrassement ou sol retourné détecté ({zone.name} - {zone.buildable_status}). "
                       f"Aucune structure visible. Surveillance activée pour analyse T3. "
                       f"Si construction confirmée en T3 et zone {zone.buildable_status} => reclassification automatique."
        }

    return None
```

#### 4.3 Scoring de Priorité (Remplace l'ancien Risk Score)
```python
def calculate_priority_score(detection) -> int:
    """
    Score de priorité d'inspection 0-100.
    Utilisé pour trier les alertes dans le dashboard et prioriser les agents.
    NE PAS appeler ce score 'risk_score illegal' — c'est un score de priorité urbanistique.
    """
    score = 0

    if detection.status == 'infraction_zonage':
        score += 80
    elif detection.status == 'sous_condition':
        score += 45
    elif detection.status == 'surveillance_preventive':
        score += 20

    # Intensité du changement NDBI
    delta_ndbi = detection.ndbi_t2 - detection.ndbi_t1
    if delta_ndbi > 0.4:
        score += 15
    elif delta_ndbi > 0.25:
        score += 8

    # Surface impactée
    if detection.surface_m2 and detection.surface_m2 > 500:
        score += 5

    return min(score, 100)
```

---

### PHASE 5: API REST (Semaine 5)

#### 5.1 Endpoints Principaux
```python
# API URLs (nomenclature mise à jour):
GET  /api/v1/zones-cadastrales/
GET  /api/v1/detections/
GET  /api/v1/detections/?alert_level=rouge
GET  /api/v1/detections/?status=infraction_zonage
POST /api/v1/detections/analyze/
GET  /api/v1/statistics/
GET  /api/v1/heatmap/
GET  /api/v1/export/geojson/
PATCH /api/v1/detections/{id}/traiter/   # Feedback terrain agent
```

#### 5.2 Serializers DRF
```python
class DetectionConstructionSerializer(serializers.ModelSerializer):
    zone_cadastrale = ZoneCadastraleSerializer(read_only=True)
    priority_score = serializers.SerializerMethodField()
    alert_label = serializers.SerializerMethodField()

    class Meta:
        model = DetectionConstruction
        fields = '__all__'

    def get_priority_score(self, obj):
        return calculate_priority_score(obj)

    def get_alert_label(self, obj):
        labels = {
            'infraction_zonage': '🔴 Infraction au Zonage',
            'sous_condition': '🟠 Inspection Requise',
            'conforme': '🟢 Développement Conforme',
            'surveillance_preventive': '🔵 Surveillance Préventive',
        }
        return labels.get(obj.status, obj.status)
```

---

### PHASE 6: FRONTEND CARTOGRAPHIQUE (Semaine 6)

#### 6.1 Interface Principale
```html
<!-- Components:
- Carte interactive Leaflet
- Filtres (date, zone_cadastrale, alert_level, status)
- Tableau détections avec colonne "Statut Conformité" (jamais "Statut Légal")
- Panneau détails avec message explicatif
- Export fonctionnalités
-->
```

#### 6.2 Couches et Couleurs
```javascript
// Layers Leaflet:
// - Cadastre (coloré par buildable_status: rouge=forbidden, orange=conditional, vert=buildable)
// - Détections nouvelles constructions (clusters colorés par alert_level)
// - Heatmap delta NDBI
// - Couche Microsoft Footprints (gris clair — bâti existant de référence)
// - Timeline changements T1 → T2

// Couleurs alertes (JAMAIS le mot "illégal" dans les labels UI):
const ALERT_COLORS = {
    'rouge':  '#E53E3E',  // Infraction au Zonage
    'orange': '#DD6B20',  // Inspection Requise
    'vert':   '#38A169',  // Développement Conforme
    'veille': '#3182CE',  // Surveillance Préventive
};
```

#### 6.3 Popup Détail (Exemple)
```javascript
// Popup pour alerte rouge:
// ⛔ Infraction au Plan de Zonage
// Zone: Z01 - Port de Treichville (Forbidden)
// Surface estimée: 450 m²
// Delta NDBI: +0.38
// Absent des données Microsoft Footprints ✓
// Absent de l'image Sentinel T1 ✓
// Score de priorité: 88/100
// ⚠️ Ce diagnostic est basé sur le plan de zonage V10.
//    La qualification juridique finale relève de l'agent cadastral.
// [Générer Rapport PDF] [Marquer comme Traité] [Signaler Faux Positif]
```

---

### PHASE 7: TÂCHES ASYNCHRONES (Semaine 7)

#### 7.1 Pipeline Celery
```python
@shared_task
def process_sentinel_image(image_id: int):
    """Preprocessing asynchrone image Sentinel: reprojection, masque nuages, normalisation."""

@shared_task
def run_conformity_analysis(t1_image_id: int, t2_image_id: int):
    """
    Pipeline complet: NDBI T1 + T2 → BSI → Détection changements
    → Vérification 4 couches → Classification → Génération alertes.
    """

@shared_task
def reclassify_preventive_alerts(t3_image_id: int):
    """
    Reclassification des détections 'surveillance_preventive' lors de l'arrivée de T3.
    Si construction formée confirmée en T3 → reclasser selon zone cadastrale.
    """

@shared_task
def generate_conformity_report(detection_id: int):
    """Génération PDF rapport de conformité urbanistique via WeasyPrint."""
```

#### 7.2 Monitoring
```python
# Dashboard monitoring:
- Status tâches Celery
- Mémoire / CPU utilisation
- Erreurs processing
- Performance requêtes
- Métriques qualité: precision, recall, faux positifs/km²
```

---

### PHASE 8: TESTS & VALIDATION (Semaine 8)

#### 8.1 Tests Unitaires
```python
# Tests à implémenter:
- Models: validation des STATUS_CHOICES (s'assurer qu'aucun 'illegal' ne passe)
- NDBI + BSI calculation accuracy
- Logique vérification 4 couches (cas Microsoft présent / absent)
- Classification 4 cas logiques (forbidden / conditional / buildable / soil)
- API responses + labels UI
- Feedback terrain (PATCH statut_traitement)
```

#### 8.2 Tests Performance
```python
# Benchmarks:
- Processing time 1 km² (objectif < 60 sec)
- Import Microsoft Footprints 658K features (objectif < 10 min)
- API response times (objectif < 500ms)
- Requêtes ST_Intersects PostGIS avec GiST index
```

---

## 🔧 DÉPENDANCES TECHNIQUES

### Python Requirements
```txt
Django>=5.2
djangorestframework>=3.14
psycopg2-binary>=2.9
celery>=5.3
redis>=5.0
gdal>=3.7
rasterio>=1.3
geopandas>=0.14
numpy>=1.24
scipy>=1.11
pillow>=10.0
weasyprint>=60.0
```

### System Dependencies
```bash
# Ubuntu/Debian:
apt-get install gdal-bin libgdal-dev
apt-get install postgresql-15-postgis-3
apt-get install redis-server

# Windows (via conda):
conda install -c conda-forge gdal
conda install -c conda-forge postgis
conda install -c conda-forge redis
```

---

## 📊 MÉTRIQUES DE SUCCÈS

### KPIs Techniques
- **Précision détection**: >85% sur zones forbidden
- **Taux faux positifs**: <15% (bâtiments existants Microsoft mal filtrés)
- **Temps processing**: <60 sec / km²
- **Disponibilité**: >99%
- **Réponse API**: <500ms

### KPIs Métier
- **Nombre alertes rouges générées** (infractions zonage)
- **Nombre alertes orange générées** (zones conditional)
- **Taux de confirmation terrain** (feedback agents)
- **Surface analysée**: 100% Treichville
- **Mise à jour**: Mensuelle automatique (ou dès nouvelle image Sentinel disponible)

---

## 🚨 RISQUES & MITIGATIONS

### Risques Techniques
1. **Faux positifs Microsoft Footprints** (bâtiments manquants dans le fichier) → Coupler avec vérification T1 Sentinel comme double filet
2. **Ambiguïté temporelle Microsoft** (date de production incertaine) → Documenter la limite dans les rapports PDF, toujours croiser avec T1 Sentinel
3. **Performance import 658K features** → Utiliser ogr2ogr ou GeoPandas chunking, filtrer la bbox Treichville en amont
4. **Précision NDBI zones mixtes** → Affiner le seuil threshold par type de zone cadastrale (zones portuaires vs résidentielles)
5. **Détection terrassement BSI** → Calibrer threshold_soil sur quelques exemples connus de Treichville avant déploiement

### Risques Métier
1. **Mauvaise interprétation "infraction_zonage" = "illégal"** → Former les agents, afficher disclaimer sur chaque alerte rouge dans l'UI
2. **Acceptation utilisateurs** → Formation + documentation claire du workflow 4 couches
3. **Maintenance** → Monitoring + logs détaillés pipeline

---

## 📅 CALENDRIER PRÉVISIONNEL

| Phase | Durée | Livrable | Status |
|-------|-------|----------|---------|
| 1. Configuration Base + Models v2 | 1 semaine | Django configuré, models révisés | ⏳ À faire |
| 2. Ingestion 4 Sources de Données | 1 semaine | Cadastre + Sentinel + Microsoft importés | ⏳ À faire |
| 3. Traitement NDBI + BSI | 1 semaine | Algorithmes calcul indices | ⏳ À faire |
| 4. Vérification 4 Couches + Classification | 1 semaine | Logique métier révisée | ⏳ À faire |
| 5. API REST | 1 semaine | Endpoints + nomenclature correcte | ⏳ À faire |
| 6. Frontend Cartographique | 1 semaine | Interface web + labels conformité | ⏳ À faire |
| 7. Tâches Asynchrones Celery | 1 semaine | Pipeline complet automatisé | ⏳ À faire |
| 8. Tests & Validation | 1 semaine | Qualité assurée | ⏳ À faire |

**Total**: 8 semaines (~2 mois)

---

## 🎯 PROCHAINES ACTIONS IMMÉDIATES

### Jour 1-3
1. **Configuration environnement** Django + PostgreSQL + PostGIS
2. **Mise à jour models** avec STATUS_CHOICES v2 (supprimer 'illegal', 'legal', 'suspicious')
3. **Import cadastre V10** + vérification des 19 zones

### Jour 4-7
1. **Import Microsoft Footprints** — filtrage bbox Treichville + index GiST
2. **Import images Sentinel T1 et T2** — validation alignement géographique
3. **Setup pipeline** calcul NDBI + BSI

### Jour 8-14
1. **Implémentation vérification 4 couches** avec tests sur cas connus
2. **Classification 4 cas logiques** + tests unitaires des statuts
3. **Début développement API** avec nouvelle nomenclature

---

## 📞 CONTACT & SUPPORT

**Développeur Lead**: [À compléter]  
**Expert SIG**: [À compléter]  
**Infrastructure**: [À compléter]

---

*Document v2.0 — Logique révisée : passage de "détection d'illégalité" à "monitoring de conformité urbanistique". La vérification en 4 couches et les 4 cas logiques remplacent intégralement l'ancienne logique 3 cas. Aucune occurrence du terme "illégal" dans le code ou les outputs utilisateurs.*