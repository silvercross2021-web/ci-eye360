import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from module1_urbanisme.models import DetectionConstruction
d = DetectionConstruction.objects.all().first()
if d:
    print(d.id, json.dumps(json.loads(d.geometry_geojson), indent=2))
