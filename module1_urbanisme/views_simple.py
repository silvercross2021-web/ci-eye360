"""
Vues simplifiées pour tester l'API sans erreurs de sérialisation
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone

from .models import ZoneCadastrale, DetectionConstruction
from .serializers_simple import ZoneCadastraleSimpleSerializer, DetectionConstructionSimpleSerializer


class DetectionSimpleViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet simplifié pour les détections"""
    
    queryset = DetectionConstruction.objects.all().select_related('zone_cadastrale')
    serializer_class = DetectionConstructionSimpleSerializer
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques simplifiées"""
        zones_stats = ZoneCadastrale.objects.aggregate(
            total_zones=Count('id'),
            zones_forbidden=Count('id', filter=Q(buildable_status='forbidden')),
            zones_conditional=Count('id', filter=Q(buildable_status='conditional')),
            zones_buildable=Count('id', filter=Q(buildable_status='buildable'))
        )
        
        detections_stats = DetectionConstruction.objects.aggregate(
            total_detections=Count('id'),
            detections_infraction=Count('id', filter=Q(status='infraction_zonage')),
            detections_surveillance=Count('id', filter=Q(status='sous_condition')),
            detections_conforme=Count('id', filter=Q(status='conforme')),
            detections_preventive=Count('id', filter=Q(status='surveillance_preventive'))
        )
        
        return Response({
            **zones_stats,
            **detections_stats,
            'last_update': timezone.now()
        })
    
    @action(detail=False, methods=['get'])
    def alertes_rouges(self, request):
        """Alertes rouges uniquement"""
        alertes = self.get_queryset().filter(status='infraction_zonage')
        serializer = self.get_serializer(alertes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def resume(self, request):
        """Résumé pour dashboard"""
        alertes_par_niveau = DetectionConstruction.objects.values('alert_level').annotate(
            count=Count('id')
        ).order_by('alert_level')
        
        detections_par_statut = DetectionConstruction.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        return Response({
            'alertes_par_niveau': list(alertes_par_niveau),
            'detections_par_statut': list(detections_par_statut)
        })
