"""
Serializers simplifiés pour éviter les erreurs de sérialisation
"""

from rest_framework import serializers
from .models import ZoneCadastrale, DetectionConstruction


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
        """Calcule le score de priorité 0-100"""
        score = 0
        
        if obj.status == 'infraction_zonage':
            score += 80
        elif obj.status == 'sous_condition':
            score += 45
        elif obj.status == 'surveillance_preventive':
            score += 20
        
        # Intensité du changement NDBI
        if obj.ndbi_t1 is not None and obj.ndbi_t2 is not None:
            delta_ndbi = obj.ndbi_t2 - obj.ndbi_t1
            if delta_ndbi > 0.4:
                score += 15
            elif delta_ndbi > 0.25:
                score += 8
        
        # Surface impactée
        if obj.surface_m2 and obj.surface_m2 > 500:
            score += 5
        
        return min(score, 100)
    
    def get_alert_label(self, obj):
        """Retourne le label avec emoji pour l'affichage"""
        labels = {
            'infraction_zonage': '🔴 Infraction au Zonage',
            'sous_condition': '🟠 Inspection Requise',
            'conforme': '🟢 Développement Conforme',
            'surveillance_preventive': '🔵 Surveillance Préventive',
        }
        return labels.get(obj.status, obj.get_status_display())
