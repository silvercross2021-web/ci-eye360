"""
URLs de l'API pour Module 1 Urbanisme
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DetectionConstructionViewSet,
    ImageSatelliteViewSet,
    ZoneCadastraleViewSet,
    MicrosoftFootprintViewSet,
    DashboardViewSet
)

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'zones-cadastrales', ZoneCadastraleViewSet)
router.register(r'images-satellite', ImageSatelliteViewSet)
router.register(r'microsoft-footprints', MicrosoftFootprintViewSet)
router.register(r'detections', DetectionConstructionViewSet, basename='detection')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

# URLs de l'API
urlpatterns = [
    path('api/v1/', include(router.urls)),
]
