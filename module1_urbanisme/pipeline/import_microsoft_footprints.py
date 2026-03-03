"""
Script d'import des Microsoft Building Footprints
Importe les bâtiments existants depuis le fichier GeoJSON Lines (658K features)
"""

import json
import os
from django.core.management.base import BaseCommand
from module1_urbanisme.models import MicrosoftFootprint
from django.db import transaction
from tqdm import tqdm


class Command(BaseCommand):
    help = 'Importe les empreintes de bâtiments Microsoft depuis le fichier GeoJSON Lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='module1_urbanisme/data_use/Abidjan_33333010.geojsonl',
            help='Chemin vers le fichier GeoJSON Lines Microsoft'
        )
        parser.add_argument(
            '--bbox',
            type=str,
            default='-4.03001,5.28501,-3.97301,5.32053',
            help='Bounding box pour filtrer Treichville (minLon,minLat,maxLon,maxLat)'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help='Taille des chunks pour l\'import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les statistiques sans importer'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limite le nombre de features à importer (pour tests)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        bbox = self.parse_bbox(options['bbox'])
        chunk_size = options['chunk_size']
        dry_run = options['dry_run']
        limit = options.get('limit')
        
        self.stdout.write(f"Import Microsoft Footprints depuis: {file_path}")
        self.stdout.write(f"BBOX Treichville: {bbox}")
        self.stdout.write(f"Chunk size: {chunk_size}")
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Fichier introuvable: {file_path}"))
            return
        
        try:
            # Compter les lignes d'abord
            total_lines = self.count_lines(file_path)
            self.stdout.write(f"Total lignes dans fichier: {total_lines:,}")
            
            if limit:
                total_lines = min(total_lines, limit)
                self.stdout.write(f"Limité à: {total_lines:,} lignes")
            
            # Import par chunks
            imported_count = 0
            skipped_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                chunk = []
                
                with tqdm(total=total_lines, desc="Import Microsoft") as pbar:
                    for i, line in enumerate(f):
                        if limit and i >= limit:
                            break
                        
                        try:
                            feature = json.loads(line.strip())
                            
                            # Filtrer par bbox
                            if self.is_in_bbox(feature, bbox):
                                chunk.append(feature)
                                
                                if len(chunk) >= chunk_size:
                                    if dry_run:
                                        imported_count += len(chunk)
                                    else:
                                        count = self.import_chunk(chunk)
                                        imported_count += count
                                    
                                    chunk = []
                                    pbar.update(len(chunk))
                            else:
                                skipped_count += 1
                            
                            pbar.update(1)
                            
                        except json.JSONDecodeError as e:
                            self.stdout.write(f"Erreur JSON ligne {i}: {e}")
                            skipped_count += 1
                        except Exception as e:
                            self.stdout.write(f"Erreur traitement ligne {i}: {e}")
                            skipped_count += 1
                    
                    # Dernier chunk
                    if chunk and not dry_run:
                        count = self.import_chunk(chunk)
                        imported_count += count
                    elif chunk and dry_run:
                        imported_count += len(chunk)
            
            # Résumé
            self.stdout.write(self.style.SUCCESS(f"\n=== RÉSUMÉ IMPORT ==="))
            self.stdout.write(f"Empreintes importées: {imported_count:,}")
            self.stdout.write(f"Empreintes ignorées (hors bbox): {skipped_count:,}")
            
            if not dry_run:
                self.print_statistics()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lors de l'import: {str(e)}"))

    def parse_bbox(self, bbox_str):
        """Parse bbox string 'minLon,minLat,maxLon,maxLat'"""
        coords = [float(x) for x in bbox_str.split(',')]
        return {
            'min_lon': coords[0],
            'min_lat': coords[1], 
            'max_lon': coords[2],
            'max_lat': coords[3]
        }
    
    def count_lines(self, file_path):
        """Compte les lignes dans le fichier"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    
    def is_in_bbox(self, feature, bbox):
        """Vérifie si la feature est dans la bounding box"""
        geometry = feature.get('geometry', {})
        coordinates = geometry.get('coordinates', [])
        
        if not coordinates:
            return False
        
        # Extraire les coordonnées du premier point
        if geometry['type'] == 'Polygon':
            coords = coordinates[0]  # Premier ring
            if coords:
                lon, lat = coords[0]
                return (bbox['min_lon'] <= lon <= bbox['max_lon'] and 
                       bbox['min_lat'] <= lat <= bbox['max_lat'])
        
        return False
    
    def import_chunk(self, chunk):
        """Import un chunk de features en base"""
        footprints = []
        
        for feature in chunk:
            try:
                footprint_data = self.parse_feature(feature)
                footprints.append(MicrosoftFootprint(**footprint_data))
            except Exception as e:
                self.stdout.write(f"Erreur parsing feature: {e}")
        
        if footprints:
            with transaction.atomic():
                MicrosoftFootprint.objects.bulk_create(footprints, batch_size=500)
        
        return len(footprints)
    
    def parse_feature(self, feature):
        """Extrait les données d'une feature GeoJSON"""
        geometry = feature.get('geometry')
        properties = feature.get('properties', {})
        
        # Stocker la géométrie en GeoJSON string
        return {
            'geometry_geojson': json.dumps(geometry),
            'source_file': 'Abidjan_33333010.geojsonl',
            'date_reference': '~2023-2024'
        }
    
    def print_statistics(self):
        """Affiche les statistiques d'import"""
        self.stdout.write(self.style.SUCCESS(f"\n=== STATISTIQUES ==="))
        
        total = MicrosoftFootprint.objects.count()
        self.stdout.write(f"Total empreintes: {total:,}")
        
        # Surface totale estimée (approximatif)
        # Note: calcul de surface sur des polygones peut être lourd
        self.stdout.write("Note: Calcul de surface total désactivé pour performance")


# Pour utiliser ce script directement
def import_microsoft_direct(file_path=None, dry_run=True, limit=1000):
    """Import direct avec paramètres par défaut pour tests"""
    if file_path is None:
        file_path = 'module1_urbanisme/data_use/Abidjan_33333010.geojsonl'
    
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    command = Command()
    options = {
        'file': file_path,
        'dry_run': dry_run,
        'limit': limit,
        'chunk_size': 100
    }
    command.handle(**options)


if __name__ == '__main__':
    import_microsoft_direct(dry_run=True, limit=100)  # Test avec 100 lignes
