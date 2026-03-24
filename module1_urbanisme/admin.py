from django.contrib.gis import admin
from .models import ZoneCadastrale, MicrosoftFootprint, DetectionConstruction, ImageSatellite

@admin.register(ZoneCadastrale)
class ZoneCadastraleAdmin(admin.GISModelAdmin):
    list_display = ('zone_id', 'name', 'zone_type', 'buildable_status')
    search_fields = ('name', 'zone_id')
    list_filter = ('zone_type', 'buildable_status')

@admin.register(MicrosoftFootprint)
class MicrosoftFootprintAdmin(admin.GISModelAdmin):
    list_display = ('id', 'source_file', 'date_reference')
    list_filter = ('source_file',)

@admin.register(DetectionConstruction)
class DetectionConstructionAdmin(admin.GISModelAdmin):
    list_display = ('id', 'zone_cadastrale', 'status', 'alert_level', 'date_detection', 'confidence')
    list_filter = ('status', 'alert_level', 'zone_cadastrale')
    readonly_fields = ('date_detection',)

@admin.register(ImageSatellite)
class ImageSatelliteAdmin(admin.GISModelAdmin):
    list_display = ('date_acquisition', 'satellite', 'processed')
    list_filter = ('satellite', 'processed')
