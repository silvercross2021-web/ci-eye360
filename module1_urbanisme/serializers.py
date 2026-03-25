"""
Serializers Django REST Framework pour Module 1 Urbanisme
"""

from rest_framework import serializers
from .models import ZoneCadastrale, ImageSatellite, MicrosoftFootprint, DetectionConstruction


def compute_priority_score(obj) -> int:
    """Calcule le score de priorité 0-100 pour une DetectionConstruction."""
    score = 0
    if obj.status == 'infraction_zonage':
        score += 80
    elif obj.status == 'sous_condition':
        score += 45
    elif obj.status == 'surveillance_preventive':
        score += 20
    if obj.ndbi_t1 is not None and obj.ndbi_t2 is not None:
        delta_ndbi = obj.ndbi_t2 - obj.ndbi_t1
        if delta_ndbi > 0.4:
            score += 15
        elif delta_ndbi > 0.25:
            score += 8
    if obj.surface_m2 and obj.surface_m2 > 500:
        score += 5
    return min(score, 100)


class ZoneCadastraleSerializer(serializers.ModelSerializer):
    """Serializer pour les zones cadastrales"""
    
    buildable_status_display = serializers.CharField(source='get_buildable_status_display', read_only=True)
    
    class Meta:
        model = ZoneCadastrale
        fields = [
            'id', 'zone_id', 'name', 'zone_type', 'buildable_status', 
            'buildable_status_display', 'geometry_geojson', 'metadata'
        ]


class ImageSatelliteSerializer(serializers.ModelSerializer):
    """Serializer pour les images satellites"""
    
    class Meta:
        model = ImageSatellite
        fields = [
            'id', 'date_acquisition', 'satellite', 'bands', 
            'classification_map', 'processed'
        ]


class MicrosoftFootprintSerializer(serializers.ModelSerializer):
    """Serializer pour les empreintes Microsoft"""
    
    class Meta:
        model = MicrosoftFootprint
        fields = [
            'id', 'geometry_geojson', 'source_file', 'date_reference'
        ]


class DetectionConstructionSerializer(serializers.ModelSerializer):
    """Serializer pour les détections de constructions"""
    
    zone_cadastrale = ZoneCadastraleSerializer(read_only=True)
    zone_cadastrale_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    alert_level_display = serializers.CharField(source='get_alert_level_display', read_only=True)
    statut_traitement_display = serializers.CharField(source='get_statut_traitement_display', read_only=True)
    
    # Scores et labels calculés
    priority_score = serializers.SerializerMethodField()
    alert_label = serializers.SerializerMethodField()
    
    # Informations sur le traitement
    traitee_par_username = serializers.SerializerMethodField()
    # Coordonnées (Centroïde WGS84)
    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DetectionConstruction
        fields = [
            'id', 'date_detection', 'zone_cadastrale', 'zone_cadastrale_id',
            'geometry_geojson', 'ndbi_t1', 'ndbi_t2', 'bsi_value', 
            'surface_m2', 'confidence', 'present_in_microsoft', 
            'present_in_t1_sentinel', 'status', 'status_display',
            'alert_level', 'alert_level_display', 'verification_required',
            'statut_traitement', 'statut_traitement_display', 'traitee_par',
            'traitee_par_username', 'commentaire_terrain', 'date_traitement',
            'priority_score', 'alert_label', 'latitude', 'longitude'
        ]
    
    def get_priority_score(self, obj):
        return compute_priority_score(obj)
    
    def get_alert_label(self, obj):
        """Retourne le label avec emoji pour l'affichage"""
        labels = {
            'infraction_zonage': '🔴 Infraction au Zonage',
            'sous_condition': '🟠 Inspection Requise',
            'conforme': '🟢 Développement Conforme',
            'surveillance_preventive': '🔵 Surveillance Préventive',
        }
        return labels.get(obj.status, obj.get_status_display())
    
    def get_traitee_par_username(self, obj):
        """Retourne le username de l'agent qui a traité la détection"""
        if obj.traitee_par:
            return obj.traitee_par.username
        return None


class DetectionCreateSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour créer des détections"""
    
    class Meta:
        model = DetectionConstruction
        fields = [
            'zone_cadastrale', 'geometry', 'geometry_geojson', 'ndbi_t1', 'ndbi_t2',
            'bsi_value', 'surface_m2', 'confidence'
        ]
        read_only_fields = ['geometry_geojson']


class DetectionUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour le statut de traitement"""
    
    class Meta:
        model = DetectionConstruction
        fields = [
            'statut_traitement', 'commentaire_terrain'
        ]
    
    def validate(self, data):
        """Validation des mises à jour"""
        statut = data.get('statut_traitement')
        commentaire = data.get('commentaire_terrain')
        
        if statut in ['confirme', 'faux_positif'] and not commentaire:
            raise serializers.ValidationError(
                "Un commentaire est requis pour confirmer ou marquer comme faux positif"
            )
        
        return data


class StatisticsSerializer(serializers.Serializer):
    """Serializer pour les statistiques"""
    
    total_zones = serializers.IntegerField()
    zones_forbidden = serializers.IntegerField()
    zones_conditional = serializers.IntegerField()
    zones_buildable = serializers.IntegerField()
    
    total_detections = serializers.IntegerField()
    detections_infraction = serializers.IntegerField()
    detections_sous_condition = serializers.IntegerField()
    detections_conforme = serializers.IntegerField()
    detections_preventive = serializers.IntegerField()
    
    total_microsoft_footprints = serializers.IntegerField()
    
    last_update = serializers.DateTimeField()
