"""
Script d'import du cadastre V10 de Treichville
Importe les 19 zones cadastrales depuis le fichier GeoJSON
"""

import json
import os
from django.core.management.base import BaseCommand
from module1_urbanisme.models import ZoneCadastrale
from django.db.models import Count


class Command(BaseCommand):
    help = 'Importe les zones cadastrales depuis le fichier cadastre_treichville_v10.geojson'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='module1_urbanisme/data_use/cadastre_treichville_v10 (1).geojson',
            help='Chemin vers le fichier GeoJSON du cadastre'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les zones à importer sans créer en base'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Import du cadastre depuis: {file_path}")
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable: {file_path}"))
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            metadata = data.get('_metadata', {})
            
            self.stdout.write(f"Métadonnées: {metadata.get('version', 'N/A')} - {metadata.get('zones', 0)} zones")
            
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for feature in features:
                try:
                    zone_data = self.parse_feature(feature)
                    
                    if dry_run:
                        self.stdout.write(f"[DRY RUN] {zone_data['zone_id']} - {zone_data['name']} ({zone_data['buildable_status']})")
                        continue
                    
                    # Vérifier si la zone existe déjà
                    if ZoneCadastrale.objects.filter(zone_id=zone_data['zone_id']).exists():
                        self.stdout.write(f"Zone {zone_data['zone_id']} déjà existante - mise à jour")
                        zone = ZoneCadastrale.objects.get(zone_id=zone_data['zone_id'])
                        self.update_zone(zone, zone_data)
                    else:
                        zone = ZoneCadastrale.objects.create(**zone_data)
                        self.stdout.write(f"Créé: {zone}")
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Erreur avec feature {feature.get('id', 'Unknown')}: {str(e)}")
                    skipped_count += 1
            
            # Résumé
            self.stdout.write(self.style.SUCCESS(f"\n=== RÉSUMÉ IMPORT ==="))
            self.stdout.write(f"Zones importées: {imported_count}")
            self.stdout.write(f"Zones ignorées: {skipped_count}")
            
            if errors:
                self.stdout.write(self.style.ERROR(f"\nErreurs ({len(errors)}):"))
                for error in errors[:10]:  # Limiter l'affichage des erreurs
                    self.stdout.write(f"  - {error}")
                if len(errors) > 10:
                    self.stdout.write(f"  ... et {len(errors) - 10} autres erreurs")
            
            # Statistiques
            if not dry_run:
                self.print_statistics()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de l'import: {str(e)}"))

    def parse_feature(self, feature):
        """Extrait les données d'une feature GeoJSON"""
        properties = feature.get('properties', {})
        geometry = feature.get('geometry')
        
        # Conversion du statut
        zone_status = properties.get('zone_status', 'buildable')
        if zone_status == 'forbidden':
            buildable_status = 'forbidden'
        elif zone_status == 'conditional':
            buildable_status = 'conditional'
        else:
            buildable_status = 'buildable'
        
        return {
            'zone_id': properties.get('zone_id'),
            'name': properties.get('name'),
            'zone_type': properties.get('zone_type'),
            'buildable_status': buildable_status,
            'geometry_geojson': json.dumps(geometry),  # Stocker en GeoJSON string
            'metadata': {
                'description': properties.get('description', ''),
                'bbox': feature.get('bbox'),
                'zone_status_original': zone_status
            }
        }
    
    def update_zone(self, zone, zone_data):
        """Met à jour une zone existante"""
        zone.name = zone_data['name']
        zone.zone_type = zone_data['zone_type']
        zone.buildable_status = zone_data['buildable_status']
        zone.geometry_geojson = zone_data['geometry_geojson']
        zone.metadata = zone_data['metadata']
        zone.save()
    
    def print_statistics(self):
        """Affiche les statistiques d'import"""
        self.stdout.write(self.style.SUCCESS(f"\n=== STATISTIQUES ==="))
        
        stats = ZoneCadastrale.objects.values('buildable_status').annotate(count=models.Count('id'))
        
        for stat in stats:
            status_label = dict(ZoneCadastrale.BUILDABLE_STATUS_CHOICES).get(stat['buildable_status'], stat['buildable_status'])
            self.stdout.write(f"{status_label}: {stat['count']} zones")
        
        total = ZoneCadastrale.objects.count()
        self.stdout.write(f"Total: {total} zones")


# Pour utiliser ce script directement (hors Django management command)
def import_cadastre_direct(file_path=None, dry_run=False):
    """Import direct du cadastre"""
    if file_path is None:
        file_path = 'module1_urbanisme/data_use/cadastre_treichville_v10 (1).geojson'
    
    # Configuration Django manuelle si nécessaire
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    command = Command()
    options = {'file': file_path, 'dry_run': dry_run}
    command.handle(**options)


if __name__ == '__main__':
    import_cadastre_direct(dry_run=True)  # Test dry-run par défaut
