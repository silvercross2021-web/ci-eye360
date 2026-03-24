from django.contrib.gis.db import models
from django.contrib.auth.models import User


class ZoneCadastrale(models.Model):
    """Zone cadastrale du plan de zonage V10 de Treichville"""
    
    BUILDABLE_STATUS_CHOICES = [
        ('forbidden', 'Zone Interdite'),
        ('conditional', 'Zone Sous Condition'),
        ('buildable', 'Zone Constructible'),
    ]
    
    zone_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    zone_type = models.CharField(max_length=50)  # harbour, residential, commercial, etc.
    buildable_status = models.CharField(max_length=20, choices=BUILDABLE_STATUS_CHOICES)
    # GÉOMÉTRIE POSTGIS NATIVE
    geometry = models.PolygonField(srid=4326, null=True, help_text="Géométrie spatiale PostGIS")
    metadata = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = "Zone Cadastrale"
        verbose_name_plural = "Zones Cadastrales"
    
    def __str__(self):
        return f"{self.zone_id} - {self.name}"

    @property
    def geometry_geojson(self):
        """Propriété de compatibilité pour le frontend : retourne le GeoJSON de la géométrie."""
        return self.geometry.json if self.geometry else None


class ImageSatellite(models.Model):
    """Image satellite Sentinel-2 pour traitement NDBI"""
    
    date_acquisition = models.DateField()
    satellite = models.CharField(max_length=50, default='Sentinel-2')
    bands = models.JSONField(default=dict)  # Chemins vers les fichiers B04, B08, B11, B12
    classification_map = models.CharField(max_length=500, blank=True, null=True,
        help_text="Chemin absolu vers le fichier SCL (Scene Classification Layer)")
    processed = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Image Satellite"
        verbose_name_plural = "Images Satellites"
    
    def __str__(self):
        return f"{self.satellite} - {self.date_acquisition}"


class MicrosoftFootprint(models.Model):
    """
    Bâtiments existants avant la période de surveillance (vérité terrain).
    
    Source actuelle : Google Open Buildings V3 (mai 2023, 50cm/pixel, CC-BY 4.0)
    Source historique : Microsoft Building Footprints (obsolète, données 2020)
    
    Le nom du modèle est conservé pour compatibilité avec les migrations existantes.
    """
    
    SOURCE_CHOICES = [
        ('Google_V3_2023', 'Google Open Buildings V3 (mai 2023)'),
        ('Google_Temporal_V1', 'Google Open Buildings Temporal V1'),
        ('Microsoft_2020', 'Microsoft Building Footprints (obsolète)'),
    ]
    
    # GÉOMÉTRIE POSTGIS NATIVE
    geometry = models.PolygonField(srid=4326, null=True, help_text="Géométrie spatiale PostGIS")
    source_file = models.CharField(max_length=255, default='google_open_buildings_v3')
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='Google_V3_2023')
    date_reference = models.CharField(max_length=50, default='2023-05')
    confidence_score = models.FloatField(
        null=True, blank=True,
        help_text="Score de confiance Google Open Buildings (0.65-1.0). Rouge: 0.65-0.70, Jaune: 0.70-0.75, Vert: >=0.75"
    )
    
    class Meta:
        verbose_name = "Empreinte Bâtiment"
        verbose_name_plural = "Empreintes Bâtiments"
        indexes = [
            models.Index(fields=['source_file']),
            models.Index(fields=['source']),
            models.Index(fields=['confidence_score']),
        ]
    
    def __str__(self):
        return f"Building Footprint {self.id} ({self.source})"


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

    TRAITEMENT_CHOICES = [
        ('en_attente', 'En attente'),
        ('confirme', 'Confirmé'),
        ('faux_positif', 'Faux positif'),
        ('en_investigation', 'En investigation'),
    ]

    date_detection = models.DateTimeField(auto_now_add=True)
    zone_cadastrale = models.ForeignKey(ZoneCadastrale, on_delete=models.CASCADE, null=True)
    
    # GÉOMÉTRIE POSTGIS NATIVE
    geometry = models.PolygonField(srid=4326, null=True, help_text="Géométrie spatiale PostGIS")
    
    # Indices calculés
    ndbi_t1 = models.FloatField(help_text="Valeur NDBI sur image T1 (référence)")
    ndbi_t2 = models.FloatField(help_text="Valeur NDBI sur image T2 (détection)")
    bsi_value = models.FloatField(null=True, blank=True, help_text="Bare Soil Index pour détection terrassement")
    surface_m2 = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(default=0.0)
    
    # Résultat de la vérification 4 couches
    present_in_microsoft = models.BooleanField(default=False)
    present_in_t1_sentinel = models.BooleanField(default=False)
    
    # Classification finale
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    alert_level = models.CharField(max_length=10, choices=ALERT_LEVEL_CHOICES)
    verification_required = models.BooleanField(default=True)
    
    # Feedback agent terrain
    statut_traitement = models.CharField(max_length=20, choices=TRAITEMENT_CHOICES, default='en_attente')
    traitee_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    commentaire_terrain = models.TextField(blank=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Détection de Construction"
        verbose_name_plural = "Détections de Constructions"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['alert_level']),
            models.Index(fields=['date_detection']),
            models.Index(fields=['statut_traitement']),
        ]
    
    def __str__(self):
        return f"Détection {self.id} - {self.get_status_display()} ({self.get_alert_level_display()})"

    @property
    def geometry_geojson(self):
        """Propriété de compatibilité pour le frontend : retourne le GeoJSON de la géométrie."""
        return self.geometry.json if self.geometry else None

    def get_centroid_coordinates(self):
        """
        Calcule le point central exact du polygone avec la méthode du Centroïde native PostGIS.
        Format: {'latitude': float, 'longitude': float}
        """
        try:
            if not self.geometry:
                return {"latitude": None, "longitude": None}
                
            centroid = self.geometry.centroid
            # GeoDjango Point: x=longitude, y=latitude
            return {"latitude": round(centroid.y, 6), "longitude": round(centroid.x, 6)}
        except Exception:
            pass
            
        return {"latitude": None, "longitude": None}

    @property
    def latitude(self):
        return self.get_centroid_coordinates().get("latitude")

    @property
    def longitude(self):
        return self.get_centroid_coordinates().get("longitude")
