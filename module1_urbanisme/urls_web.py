"""
URLs pour l'interface web de CIV-Eye Module 1
"""

from django.urls import path
from . import views_web

urlpatterns = [
    # Pages principales
    path('', views_web.dashboard, name='dashboard'),
    path('detections/', views_web.detections_list, name='detections_list'),
    path('detections/<int:detection_id>/', views_web.detection_detail, name='detection_detail'),
    
    # Zones cadastrales
    path('zones/', views_web.zones_cadastrales, name='zones_cadastrales'),
    path('zones/<str:zone_id>/', views_web.zone_detail, name='zone_detail'),
    
    # API endpoints pour l'interface
    path('api/statistics/', views_web.api_statistics, name='api_statistics'),
    path('api/detections-geojson/', views_web.api_detections_geojson, name='api_detections_geojson'),
    path('api/zones-geojson/', views_web.api_zones_geojson, name='api_zones_geojson'),
]
