import os
import django
import csv
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from module1_urbanisme.models import DetectionConstruction

def export_detections():
    detections = DetectionConstruction.objects.all().order_by('-date_detection')
    output_file = 'export_detections_gps.csv'
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(['ID', 'Date', 'Zone', 'Statut', 'Alerte', 'Latitude', 'Longitude'])
        
        for d in detections:
            date_str = d.date_detection.strftime('%Y-%m-%d %H:%M')
            zone_id = d.zone_cadastrale.zone_id if d.zone_cadastrale else "Hors cadastre"
            
            writer.writerow([
                d.id,
                date_str,
                zone_id,
                d.get_status_display(),
                d.get_alert_level_display(),
                d.latitude,
                d.longitude
            ])
            
    print(f"✅ Export réussi : {len(detections)} détections enregistrées dans '{output_file}'")

if __name__ == "__main__":
    export_detections()
