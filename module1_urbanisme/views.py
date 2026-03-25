"""
Vues Django REST Framework pour Module 1 Urbanisme
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q
from django.utils import timezone

from .models import ZoneCadastrale, ImageSatellite, MicrosoftFootprint, DetectionConstruction
from .serializers import (
    ZoneCadastraleSerializer, ImageSatelliteSerializer, 
    MicrosoftFootprintSerializer, DetectionConstructionSerializer,
    DetectionCreateSerializer, DetectionUpdateSerializer, StatisticsSerializer
)


class ZoneCadastraleViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les zones cadastrales"""
    
    queryset = ZoneCadastrale.objects.all()
    serializer_class = ZoneCadastraleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['buildable_status', 'zone_type']
    search_fields = ['name', 'zone_id']
    ordering_fields = ['zone_id', 'name']
    ordering = ['zone_id']


class ImageSatelliteViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les images satellites"""
    
    queryset = ImageSatellite.objects.all()
    serializer_class = ImageSatelliteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['satellite', 'processed']
    ordering = ['-date_acquisition']


class MicrosoftFootprintViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les empreintes Microsoft"""
    
    queryset = MicrosoftFootprint.objects.all()
    serializer_class = MicrosoftFootprintSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['source_file']
    ordering = ['-id']


class DetectionConstructionViewSet(viewsets.ModelViewSet):
    """ViewSet pour les détections de constructions"""
    
    queryset = DetectionConstruction.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'status', 'alert_level', 'statut_traitement', 
        'zone_cadastrale', 'verification_required'
    ]
    search_fields = ['commentaire_terrain', 'zone_cadastrale__name']
    ordering_fields = ['date_detection', 'surface_m2', 'confidence', 'ndbi_t2', 'status', 'alert_level']
    ordering = ['-date_detection']
    
    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action"""
        if self.action == 'create':
            return DetectionCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DetectionUpdateSerializer
        return DetectionConstructionSerializer
    
    def get_queryset(self):
        """Optimise le queryset avec les relations"""
        return super().get_queryset().select_related('zone_cadastrale', 'traitee_par')
    
    @action(detail=True, methods=['patch'])
    def traiter(self, request, pk=None):
        """Action pour traiter une détection (agent terrain)"""
        detection = self.get_object()
        
        # Vérifier que l'utilisateur est authentifié
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentification requise'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = DetectionUpdateSerializer(
            detection, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            # Mettre à jour les champs de traitement
            detection.traitee_par = request.user
            detection.date_traitement = timezone.now()
            serializer.save()
            
            return Response(DetectionConstructionSerializer(detection).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Retourne les statistiques du système"""
        # Statistiques zones cadastrales
        zones_stats = ZoneCadastrale.objects.aggregate(
            total_zones=Count('id'),
            zones_forbidden=Count('id', filter=Q(buildable_status='forbidden')),
            zones_conditional=Count('id', filter=Q(buildable_status='conditional')),
            zones_buildable=Count('id', filter=Q(buildable_status='buildable'))
        )
        
        # Statistiques détections
        detections_stats = DetectionConstruction.objects.aggregate(
            total_detections=Count('id'),
            detections_infraction=Count('id', filter=Q(status='infraction_zonage')),
            detections_sous_condition=Count('id', filter=Q(status='sous_condition')),
            detections_conforme=Count('id', filter=Q(status='conforme')),
            detections_preventive=Count('id', filter=Q(status='surveillance_preventive'))
        )
        
        # Statistiques Microsoft
        microsoft_stats = {
            'total_microsoft_footprints': MicrosoftFootprint.objects.count()
        }
        
        # Dernière mise à jour
        last_detection = DetectionConstruction.objects.order_by('-date_detection').first()
        last_update = last_detection.date_detection if last_detection else timezone.now()
        
        # Combiner toutes les statistiques
        stats_data = {
            **zones_stats,
            **detections_stats,
            **microsoft_stats,
            'last_update': last_update
        }
        
        serializer = StatisticsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def alertes_rouges(self, request):
        """Retourne uniquement les alertes rouges (infractions au zonage)"""
        alertes = self.get_queryset().filter(status='infraction_zonage')
        page = self.paginate_queryset(alertes)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(alertes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def alertes_orange(self, request):
        """Retourne uniquement les alertes orange (zones sous conditions)"""
        alertes = self.get_queryset().filter(status='sous_condition')
        page = self.paginate_queryset(alertes)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(alertes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def en_attente(self, request):
        """Retourne les détections en attente de traitement"""
        en_attente = self.get_queryset().filter(statut_traitement='en_attente')
        page = self.paginate_queryset(en_attente)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(en_attente, many=True)
        return Response(serializer.data)


class DashboardViewSet(viewsets.GenericViewSet):
    """ViewSet pour le dashboard principal"""
    
    @action(detail=False, methods=['get'])
    def resume(self, request):
        """Retourne un résumé pour le dashboard"""
        # Nombre d'alertes par niveau
        alertes_par_niveau = DetectionConstruction.objects.values('alert_level').annotate(
            count=Count('id')
        ).order_by('alert_level')
        
        # Nombre de détections par statut
        detections_par_statut = DetectionConstruction.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Zones avec le plus de détections
        zones_plus_actives = ZoneCadastrale.objects.annotate(
            detection_count=Count('detectionconstruction')
        ).order_by('-detection_count')[:5]
        
        return Response({
            'alertes_par_niveau': list(alertes_par_niveau),
            'detections_par_statut': list(detections_par_statut),
            'zones_plus_actives': ZoneCadastraleSerializer(
                zones_plus_actives, many=True
            ).data
        })

