"""
URLs simplifiées pour tester l'API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_simple

router = DefaultRouter()
router.register(r'detections-simple', views_simple.DetectionSimpleViewSet, basename='detection-simple')

urlpatterns = [
    path('api/v2/', include(router.urls)),
]
