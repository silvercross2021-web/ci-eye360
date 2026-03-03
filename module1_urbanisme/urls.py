"""
URLs de l'API pour Module 1 Urbanisme
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'zones-cadastrales', views.ZoneCadastraleViewSet)
router.register(r'images-satellite', views.ImageSatelliteViewSet)
router.register(r'microsoft-footprints', views.MicrosoftFootprintViewSet)
router.register(r'detections', views.DetectionConstructionViewSet, basename='detection')
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')

# URLs de l'API
urlpatterns = [
    path('api/v1/', include(router.urls)),
]
