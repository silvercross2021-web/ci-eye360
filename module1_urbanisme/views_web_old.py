"""
Vues web pour l'interface utilisateur de CIV-Eye Module 1
"""

from django.shortcuts import render
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
import json

from .models import ZoneCadastrale, DetectionConstruction, MicrosoftFootprint


def dashboard(request):
    """Page principale du dashboard"""
    # Statistiques générales
    zones_stats = ZoneCadastrale.objects.aggregate(
        total_zones=Count('id'),
        zones_forbidden=Count('id', filter=Q(buildable_status='forbidden')),
        zones_conditional=Count('id', filter=Q(buildable_status='conditional')),
        zones_buildable=Count('id', filter=Q(buildable_status='buildable'))
    )
    
    detections_stats = DetectionConstruction.objects.aggregate(
        total_detections=Count('id'),
        detections_infraction=Count('id', filter=Q(status='infraction_zonage')),
        detections_surveillance=Count('id', filter=Q(status='surveillance_preventive')),
        detections_conforme=Count('id', filter=Q(status='conforme')),
        detections_preventive=Count('id', filter=Q(status='surveillance_preventive'))
    )
    
    # Alertes par niveau
    alertes_par_niveau = DetectionConstruction.objects.values('alert_level').annotate(
        count=Count('id')
    ).order_by('alert_level')
    
    # Dernières détections
    dernieres_detections = DetectionConstruction.objects.select_related('zone_cadastrale').order_by('-date_detection')[:10]
    
    context = {
        'zones_stats': zones_stats,
        'detections_stats': detections_stats,
        'alertes_par_niveau': list(alertes_par_niveau),
        'dernieres_detections': dernieres_detections,
        'total_detections': detections_stats['total_detections']
    }
    
    return render(request, 'module1/dashboard.html', context)


def detections_list(request):
    """Liste complète des détections avec filtres"""
    status_filter = request.GET.get('status')
    alert_level_filter = request.GET.get('alert_level')
    
    detections = DetectionConstruction.objects.select_related('zone_cadastrale').order_by('-date_detection')
    
    if status_filter:
        detections = detections.filter(status=status_filter)
    
    if alert_level_filter:
        detections = detections.filter(alert_level=alert_level_filter)
    
    context = {
        'detections': detections,
        'status_filter': status_filter,
        'alert_level_filter': alert_level_filter,
        'status_choices': DetectionConstruction.STATUS_CHOICES,
        'alert_level_choices': DetectionConstruction.ALERT_LEVEL_CHOICES
    }
    
    return render(request, 'module1/detections_list.html', context)


def detection_detail(request, detection_id):
    """Détail d'une détection spécifique"""
    try:
        detection = DetectionConstruction.objects.select_related('zone_cadastrale').get(id=detection_id)
        
        # Extraire la géométrie pour la carte
        geometry = None
        if detection.geometry_geojson:
            try:
                geometry = json.loads(detection.geometry_geojson)
            except json.JSONDecodeError:
                pass
        
        context = {
            'detection': detection,
            'geometry': geometry,
            'zone_geometry': None
        }
        
        if detection.zone_cadastrale and detection.zone_cadastrale.geometry_geojson:
            try:
                context['zone_geometry'] = json.loads(detection.zone_cadastrale.geometry_geojson)
            except json.JSONDecodeError:
                pass
        
        return render(request, 'module1/detection_detail.html', context)
        
    except DetectionConstruction.DoesNotExist:
        return render(request, 'module1/404.html', status=404)


def zones_cadastrales(request):
    """Liste des zones cadastrales avec leurs statistiques"""
    zones = ZoneCadastrale.objects.annotate(
        detection_count=Count('detectionconstruction')
    ).order_by('zone_id')
    
    context = {
        'zones': zones
    }
    
    return render(request, 'module1/zones_cadastrales.html', context)


def zone_detail(request, zone_id):
    """Détail d'une zone cadastrale avec ses détections"""
    try:
        zone = ZoneCadastrale.objects.get(zone_id=zone_id)
        detections = DetectionConstruction.objects.filter(zone_cadastrale=zone).order_by('-date_detection')
        
        context = {
            'zone': zone,
            'detections': detections,
            'detection_count': detections.count()
        }
        
        return render(request, 'module1/zone_detail.html', context)
        
    except ZoneCadastrale.DoesNotExist:
        return render(request, 'module1/404.html', status=404)


def api_statistics(request):
    """API endpoint pour les statistiques (JSON)"""
    zones_stats = ZoneCadastrale.objects.aggregate(
        total_zones=Count('id'),
        zones_forbidden=Count('id', filter=Q(buildable_status='forbidden')),
        zones_conditional=Count('id', filter=Q(buildable_status='conditional')),
        zones_buildable=Count('id', filter=Q(buildable_status='buildable'))
    )
    
    detections_stats = DetectionConstruction.objects.aggregate(
        total_detections=Count('id'),
        detections_infraction=Count('id', filter=Q(status='infraction_zonage')),
        detections_surveillance=Count('id', filter=Q(status='surveillance_preventive')),
        detections_conforme=Count('id', filter=Q(status='conforme')),
        detections_preventive=Count('id', filter=Q(status='surveillance_preventive'))
    )
    
    return JsonResponse({
        **zones_stats,
        **detections_stats,
        'last_update': timezone.now().isoformat()
    })


def api_detections_geojson(request):
    """API endpoint pour les détections en GeoJSON"""
    detections = DetectionConstruction.objects.select_related('zone_cadastrale').all()
    
    features = []
    for detection in detections:
        try:
            geometry = json.loads(detection.geometry_geojson) if detection.geometry_geojson else None
            
            if geometry:
                feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": detection.id,
                        "status": detection.status,
                        "alert_level": detection.alert_level,
                        "ndbi_t1": detection.ndbi_t1,
                        "ndbi_t2": detection.ndbi_t2,
                        "surface_m2": detection.surface_m2,
                        "confidence": detection.confidence,
                        "zone_id": detection.zone_cadastrale.zone_id if detection.zone_cadastrale else None,
                        "zone_name": detection.zone_cadastrale.name if detection.zone_cadastrale else None,
                        "alert_label": {
                            'infraction_zonage': '🔴 Infraction au Zonage',
                            'sous_condition': '🟠 Inspection Requise',
                            'conforme': '🟢 Développement Conforme',
                            'surveillance_preventive': '🔵 Surveillance Préventive',
                        }.get(detection.status, detection.status)
                    }
                }
                features.append(feature)
        except (json.JSONDecodeError, KeyError):
            continue
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return JsonResponse(geojson)


def api_zones_geojson(request):
    """API endpoint pour les zones cadastrales en GeoJSON"""
    zones = ZoneCadastrale.objects.all()
    
    features = []
    for zone in zones:
        try:
            geometry = json.loads(zone.geometry_geojson) if zone.geometry_geojson else None
            
            if geometry:
                feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": zone.id,
                        "zone_id": zone.zone_id,
                        "name": zone.name,
                        "zone_type": zone.zone_type,
                        "buildable_status": zone.buildable_status,
                        "buildable_status_display": zone.get_buildable_status_display(),
                        "color": {
                            'forbidden': '#ff4444',
                            'conditional': '#ff9944',
                            'buildable': '#44ff44'
                        }.get(zone.buildable_status, '#888888')
                    }
                }
                features.append(feature)
        except (json.JSONDecodeError, KeyError):
            continue
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return JsonResponse(geojson)
