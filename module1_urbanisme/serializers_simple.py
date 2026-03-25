"""
Serializers simplifiés pour éviter les erreurs de sérialisation
"""

from rest_framework import serializers
from .models import ZoneCadastrale, DetectionConstruction
from .serializers import compute_priority_score


class ZoneCadastraleSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour les zones cadastrales"""
    
    class Meta:
        model = ZoneCadastrale
        fields = ['id', 'zone_id', 'name', 'zone_type', 'buildable_status']


class DetectionConstructionSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour les détections"""
    
    zone_cadastrale = ZoneCadastraleSimpleSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    alert_level_display = serializers.CharField(source='get_alert_level_display', read_only=True)
    priority_score = serializers.SerializerMethodField()
    alert_label = serializers.SerializerMethodField()
    
    class Meta:
        model = DetectionConstruction
        fields = [
            'id', 'date_detection', 'zone_cadastrale', 'geometry_geojson',
            'ndbi_t1', 'ndbi_t2', 'bsi_value', 'surface_m2', 'confidence',
            'present_in_microsoft', 'present_in_t1_sentinel', 'status', 'status_display',
            'alert_level', 'alert_level_display', 'verification_required',
            'statut_traitement', 'priority_score', 'alert_label'
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
