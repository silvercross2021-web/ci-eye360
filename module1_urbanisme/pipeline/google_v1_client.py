import os
import logging
import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class GoogleV1Client:
    """
    Client expert pour interroger Google Open Buildings Temporal V1 via Earth Engine.
    OPTIMISÉ : Analyse de zone (Surface) plutôt que de point pour une fiabilité 100%.
    """
    COLLECTION_ID = "GOOGLE/Research/open-buildings-temporal/v1"

    def __init__(self):
        self.ee = self._init_gee()
        self.is_ready = self.ee is not None

    def _init_gee(self):
        try:
            import ee
            project_id = os.getenv("GEE_PROJECT_ID", "")
            if not project_id:
                logger.warning("V1 Client : GEE_PROJECT_ID manquant dans .env")
                return None
            ee.Initialize(project=project_id)
            return ee
        except Exception as e:
            logger.error(f"V1 Client : Erreur initialisation GEE : {e}")
            return None

    def check_presence_area(self, geometry_geojson: dict, target_date: str) -> Dict:
        """
        Vérifie la probabilité de présence sur TOUTE la surface du polygone détecté.
        Plus robuste contre les imprécisions GPS qu'un simple point de centre.
        """
        if not self.is_ready:
            return {'found': False, 'confidence': 0.0, 'date_snapshot': None, 'error': 'GEE not ready'}

        try:
            # Convertir GeoJSON en Géométrie EE
            poly = self.ee.Geometry(geometry_geojson)
            
            # Charger la collection temporelle et filtrer sur la zone
            coll = self.ee.ImageCollection(self.COLLECTION_ID).filterBounds(poly)
            
            # Trouver l'image la plus proche (2016-2023)
            target_ts = datetime.datetime.strptime(target_date, "%Y-%m-%d").timestamp()
            
            def add_time_diff(img):
                img_ts = self.ee.Number(img.get('imagery_start_time_epoch_s'))
                diff = img_ts.subtract(target_ts).abs()
                return img.set('time_diff', diff)

            closest_img = coll.map(add_time_diff).sort('time_diff').first()
            
            # --- ANALYSE DE SURFACE ---
            # On demande à Google de calculer la probabilité MAXIMALE sur toute la zone
            # Si un bâtiment est présent n'importe où dans notre zone détectée, on l'attrape.
            stats = closest_img.reduceRegion(
                reducer=self.ee.Reducer.max(),
                geometry=poly,
                scale=10,  # Résolution Sentinel-2
                maxPixels=100000
            ).getInfo()
            
            p_score = float(stats.get('building_presence', 0) or 0) / 255.0
            h_score = float(stats.get('building_height', 0) or 0)
            f_score = float(stats.get('building_fractional_count', 0) or 0)
            
            # CRITÈRES EXPERTS CI-EYE :
            # Un bâtiment est considéré comme déjà présent si :
            # 1. Probabilité > 40% (0.4)
            # 2. OU Hauteur > 2.0 mètres
            # 3. OU Compte > 0.1 (présence partielle détectée)
            found = (p_score >= 0.4) or (h_score >= 2.0) or (f_score >= 0.1)
            
            # Confiance agrégée (on prend le max normalisé)
            confidence = max(p_score, min(1.0, h_score / 15.0), min(1.0, f_score * 5))

            # Récupérer la date réelle du snapshot
            info = closest_img.getInfo()
            t_start = info.get('properties', {}).get('imagery_start_time_epoch_s', 0)
            d_snapshot = datetime.datetime.utcfromtimestamp(t_start).strftime("%Y-%m-%d") if t_start else "unknown"

            return {
                'found': found,
                'confidence': round(confidence, 2),
                'date_snapshot': d_snapshot,
                'details': {
                    'prob': round(p_score, 2),
                    'height': round(h_score, 1),
                    'count': round(f_score, 2)
                },
                'error': None
            }

        except Exception as e:
            logger.error(f"V1 Client : Erreur check_presence_area : {e}")
            return {'found': False, 'confidence': 0.0, 'date_snapshot': None, 'error': str(e)}

if __name__ == "__main__":
    # TEST DE STRESS EXPERT (Treichville)
    import json
    from dotenv import load_dotenv
    load_dotenv()
    client = GoogleV1Client()
    
    # 1. Zone Bâtie Historique (Port)
    poly_built = {"type": "Polygon", "coordinates": [[[-4.008, 5.307], [-4.004, 5.307], [-4.004, 5.303], [-4.008, 5.303], [-4.008, 5.307]]]}
    
    # 2. Zone Vide (Dépôt sable/lagune)
    poly_empty = {"type": "Polygon", "coordinates": [[[-4.030, 5.286], [-4.028, 5.286], [-4.028, 5.284], [-4.030, 5.284], [-4.030, 5.286]]]}

    if client.is_ready:
        print("T1: Construction historique...")
        print(client.check_presence_area(poly_built, "2024-02-15"))
        print("\nT2: Terrain nu...")
        print(client.check_presence_area(poly_empty, "2024-02-15"))
