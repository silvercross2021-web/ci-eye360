"""
Logique de vérification en 4 couches pour le Module 1 Urbanisme
Pipeline de détection et classification des constructions

Couche 1: Microsoft Footprints (vérité terrain)
Couche 2: Sentinel T1 (référence 2024)
Couche 3: Sentinel T2 (détection 2025)
Couche 4: Cadastre V10 (classification)

CORRECTIFS APPLIQUÉS:
  - A1: Couche 1 utilise vrai test AABB (plus de hash MD5 aléatoire)
  - A2: Couche 4 utilise Shapely pour intersection spatiale réelle
  - A3: alert_level = 'veille' (conforme aux ALERT_LEVEL_CHOICES du modèle)
"""

import json
import logging
from typing import Dict, List, Optional

from django.db.models import Q
from module1_urbanisme.models import ZoneCadastrale, MicrosoftFootprint, DetectionConstruction

logger = logging.getLogger(__name__)

# Tolérance spatiale (~10m en degrés à la latitude d'Abidjan)
SPATIAL_TOLERANCE = 0.0001


class Verification4Couches:
    """Implémentation de la logique de vérification en 4 couches."""

    def __init__(self):
        self.logger = logger

    def verify_detection(
        self,
        geometry_geojson: str,
        ndbi_t1_val: float,
        ndbi_t2_val: float,
        bsi_val: Optional[float] = None,
        change_type: str = 'new_construction',
    ) -> Optional[Dict]:
        """
        Pipeline complet de vérification en 4 couches.

        Args:
            geometry_geojson: Géométrie de la détection en GeoJSON (WGS84)
            ndbi_t1_val:      Valeur NDBI période T1
            ndbi_t2_val:      Valeur NDBI période T2
            bsi_val:          Valeur BSI (optionnel)
            change_type:      'new_construction' | 'soil_activity'

        Returns:
            Dict avec classification et détails, ou None si bâtiment déjà existant.
        """
        try:
            # ── Couche 1 : Vérification Microsoft Footprints ──────────────
            present_microsoft = self._is_in_microsoft_footprints(geometry_geojson)
            if present_microsoft:
                self.logger.info("Couche 1 — Bâtiment déjà présent dans Microsoft Footprints → ignoré")
                return None

            # ── Couche 2 : Vérification Sentinel T1 ──────────────────────
            if ndbi_t1_val > 0.2:
                self.logger.info(
                    f"Couche 2 — NDBI_T1={ndbi_t1_val:.3f} > 0.2 → bâtiment existait en 2024 → ignoré"
                )
                return None

            # ── Couche 3 : Validation cohérence du changement ────────────
            if not self._is_valid_change(ndbi_t1_val, ndbi_t2_val, change_type):
                self.logger.warning("Couche 3 — Changement incohérent → ignoré")
                return None

            # ── Couche 4 : Classification cadastrale ─────────────────────
            classification = self._classify_by_zoning(geometry_geojson, change_type, bsi_val)
            return classification

        except Exception as e:
            self.logger.error(f"Erreur vérification 4 couches: {str(e)}", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────────────────
    # COUCHE 1 — Microsoft Footprints
    # CORRECTIF A1 : vrai test d'overlap AABB, plus de hash MD5 aléatoire
    # ─────────────────────────────────────────────────────────────────────
    def _is_in_microsoft_footprints(self, geometry_geojson: str) -> bool:
        """
        Couche 1 : Vérifie si la géométrie intersecte un bâtiment Microsoft existant.

        Utilise un test Axis-Aligned Bounding Box (AABB) compatible SQLite.
        → Migration vers ST_Intersects PostGIS recommandée pour la production.
        """
        try:
            geometry_data = json.loads(geometry_geojson)
            if geometry_data.get('type') != 'Polygon':
                return False

            coords = geometry_data.get('coordinates', [[]])[0]
            if not coords:
                return False

            # Bounding box de la détection candidate
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            cand_min_lon = min(lons) - SPATIAL_TOLERANCE
            cand_max_lon = max(lons) + SPATIAL_TOLERANCE
            cand_min_lat = min(lats) - SPATIAL_TOLERANCE
            cand_max_lat = max(lats) + SPATIAL_TOLERANCE

            # Parcourir les empreintes Microsoft (déjà filtrées sur la BBOX Treichville)
            for footprint in MicrosoftFootprint.objects.all().iterator(chunk_size=500):
                try:
                    fp_geom = json.loads(footprint.geometry_geojson)
                    fp_coords = fp_geom.get('coordinates', [[]])[0]
                    if not fp_coords:
                        continue

                    fp_lons = [c[0] for c in fp_coords]
                    fp_lats = [c[1] for c in fp_coords]
                    fp_min_lon = min(fp_lons)
                    fp_max_lon = max(fp_lons)
                    fp_min_lat = min(fp_lats)
                    fp_max_lat = max(fp_lats)

                    # Test de chevauchement AABB
                    overlaps = (
                        cand_min_lon < fp_max_lon
                        and cand_max_lon > fp_min_lon
                        and cand_min_lat < fp_max_lat
                        and cand_max_lat > fp_min_lat
                    )
                    if overlaps:
                        self.logger.info("Couche 1 — Chevauchement AABB avec empreinte Microsoft détectée")
                        return True

                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue

            return False

        except Exception as e:
            self.logger.error(f"Couche 1 — Erreur vérification Microsoft: {str(e)}")
            # En cas d'erreur, laisser passer (ne pas filtrer abusivement)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # COUCHE 2/3 — Validation du changement spectral
    # ─────────────────────────────────────────────────────────────────────
    def _is_valid_change(self, ndbi_t1: float, ndbi_t2: float, change_type: str) -> bool:
        """
        Couche 3 : Vérifie la cohérence du changement spectral détecté.
        """
        try:
            if change_type == 'new_construction':
                # Nouvelle construction : NDBI passe de ≤0.2 à >0.2
                return ndbi_t2 > 0.2 and ndbi_t1 <= 0.2

            elif change_type == 'soil_activity':
                # Terrassement : NDBI modéré, pas encore de bâtiment formé
                return ndbi_t2 <= 0.2

            return False

        except Exception as e:
            self.logger.error(f"Couche 3 — Erreur validation: {str(e)}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # COUCHE 4 — Classification cadastrale
    # CORRECTIF A2 : intersection spatiale réelle via Shapely
    # ─────────────────────────────────────────────────────────────────────
    def _classify_by_zoning(
        self, geometry_geojson: str, change_type: str, bsi_val: Optional[float]
    ) -> Dict:
        """
        Couche 4 : Classification selon le zonage cadastral V10.
        Utilise Shapely pour un test d'intersection géographique réel.
        """
        try:
            from shapely.geometry import shape

            candidate_geom = shape(json.loads(geometry_geojson))
            centroid = candidate_geom.centroid

            matched_zone = None
            best_overlap_area = 0.0

            for zone in ZoneCadastrale.objects.all():
                try:
                    zone_geom = shape(json.loads(zone.geometry_geojson))

                    # Test 1 : le centroid est-il dans la zone ? (cas le plus fréquent)
                    if zone_geom.contains(centroid):
                        matched_zone = zone
                        break

                    # Test 2 : intersection partielle (bord de zone)
                    if zone_geom.intersects(candidate_geom):
                        overlap_area = zone_geom.intersection(candidate_geom).area
                        if overlap_area > best_overlap_area:
                            best_overlap_area = overlap_area
                            matched_zone = zone

                except Exception:
                    continue

            if not matched_zone:
                return {
                    'status': 'sous_condition',
                    'alert_level': 'orange',
                    'message': (
                        'Construction hors périmètre cadastral connu. '
                        'Inspection terrain recommandée avant toute décision.'
                    ),
                    'zone_id': None,
                    'zone_name': 'Hors cadastre',
                    'confidence': 0.5,
                }

            if change_type == 'new_construction':
                return self._classify_new_construction(matched_zone)
            elif change_type == 'soil_activity':
                return self._classify_soil_activity(matched_zone)
            else:
                return self._classify_default(matched_zone)

        except ImportError:
            self.logger.error(
                "Shapely non installé ! Exécuter : pip install shapely>=2.0"
            )
            raise RuntimeError(
                "Shapely est requis pour la classification spatiale. "
                "Installer avec : pip install shapely>=2.0"
            )
        except Exception as e:
            self.logger.error(f"Couche 4 — Erreur classification: {str(e)}", exc_info=True)
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': 'Erreur de classification — inspection recommandée',
                'confidence': 0.3,
            }

    def _classify_new_construction(self, zone: ZoneCadastrale) -> Dict:
        """Classification pour nouvelle construction (3 cas logiques)."""
        zone_status = zone.buildable_status

        # CAS 1 — INFRACTION AU ZONAGE (Alerte Rouge)
        if zone_status == 'forbidden':
            return {
                'status': 'infraction_zonage',
                'alert_level': 'rouge',
                'message': (
                    f"Nouvelle construction détectée en Zone Interdite ({zone.name}). "
                    f"Le plan de zonage V10 interdit la construction dans cette zone. "
                    f"Transmission recommandée à l'agent cadastral pour vérification terrain."
                ),
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'confidence': 0.9,
            }

        # CAS 2 — CONSTRUCTION SOUS CONDITION (Alerte Orange)
        elif zone_status == 'conditional':
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': (
                    f"Nouvelle construction détectée en Zone Sous Condition ({zone.name}). "
                    f"Vérification du respect des servitudes de sécurité requise."
                ),
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'confidence': 0.8,
            }

        # CAS 3 — DÉVELOPPEMENT CONFORME (Notification Verte)
        elif zone_status == 'buildable':
            return {
                'status': 'conforme',
                'alert_level': 'vert',
                'message': (
                    f"Nouvelle construction en Zone Constructible ({zone.name}). "
                    f"Développement urbain conforme au zonage. Enregistrement sans alerte."
                ),
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'confidence': 0.7,
            }

        # Cas par défaut (statut inconnu)
        else:
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': f"Statut de zone inconnu ({zone.buildable_status}). Inspection requise.",
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'confidence': 0.5,
            }

    def _classify_soil_activity(self, zone: ZoneCadastrale) -> Dict:
        """
        Classification pour activité de sol (terrassement).

        CORRECTIF A3 : alert_level = 'veille' (conforme à ALERT_LEVEL_CHOICES)
        L'ancienne valeur 'surveillance_preventive' causait un crash à l'insertion BDD.
        """
        zone_status = zone.buildable_status
        return {
            'status': 'surveillance_preventive',
            'alert_level': 'veille',   # ← CORRECTIF A3 (était 'surveillance_preventive')
            'message': (
                f"Terrassement ou sol retourné détecté ({zone.name} — {zone_status}). "
                f"Aucune structure visible pour l'instant. "
                f"Surveillance activée pour analyse T3. "
                f"Si construction confirmée en T3 → reclassification automatique."
            ),
            'zone_id': zone.zone_id,
            'zone_name': zone.name,
            'zone_type': zone.zone_type,
            'confidence': 0.6,
        }

    def _classify_default(self, zone: ZoneCadastrale) -> Dict:
        """Classification par défaut."""
        return {
            'status': 'sous_condition',
            'alert_level': 'orange',
            'message': f"Changement détecté dans {zone.name}. Classification par défaut.",
            'zone_id': zone.zone_id,
            'zone_name': zone.name,
            'confidence': 0.5,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline de création d'enregistrements
# ─────────────────────────────────────────────────────────────────────────────

class DetectionPipeline:
    """Pipeline complet de détection et création d'enregistrements BDD."""

    def __init__(self):
        self.verifier = Verification4Couches()
        self.logger = logging.getLogger(__name__)

    def process_detection_regions(
        self, regions: List[Dict], image_metadata: Dict
    ) -> List[DetectionConstruction]:
        """
        Traite une liste de régions détectées et crée les enregistrements.

        Args:
            regions:        Liste des régions (avec geometry_geojson en WGS84)
            image_metadata: Métadonnées des images satellites

        Returns:
            Liste des DetectionConstruction créées.
        """
        created_detections = []

        for region in regions:
            try:
                ndbi_values = self._extract_region_values(region, image_metadata)

                classification = self.verifier.verify_detection(
                    geometry_geojson=region.get('geometry_geojson', '{}'),
                    ndbi_t1_val=ndbi_values.get('ndbi_t1', 0.0),
                    ndbi_t2_val=ndbi_values.get('ndbi_t2', 0.0),
                    bsi_val=ndbi_values.get('bsi'),
                    change_type=region.get('change_type', 'new_construction'),
                )

                if classification is None:
                    continue  # Bâtiment déjà existant ou changement invalide

                detection = self._create_detection_record(region, classification, ndbi_values)
                created_detections.append(detection)

            except Exception as e:
                self.logger.error(
                    f"Erreur traitement région {region.get('label', '?')}: {str(e)}",
                    exc_info=True,
                )
                continue

        self.logger.info(f"Pipeline terminé : {len(created_detections)} détections créées")
        return created_detections

    def _extract_region_values(self, region: Dict, image_metadata: Dict) -> Dict:
        """Extrait les valeurs NDBI/BSI moyennes pour une région."""
        # Les valeurs réelles sont passées depuis run_detection.py via le dict region
        return {
            'ndbi_t1': region.get('ndbi_t1', 0.1),
            'ndbi_t2': region.get('ndbi_t2', 0.4),
            'bsi': region.get('bsi', None),
        }

    def _create_detection_record(
        self, region: Dict, classification: Dict, ndbi_values: Dict
    ) -> DetectionConstruction:
        """Crée un enregistrement DetectionConstruction en base."""

        zone = None
        if classification.get('zone_id'):
            try:
                zone = ZoneCadastrale.objects.get(zone_id=classification['zone_id'])
            except ZoneCadastrale.DoesNotExist:
                pass

        # Surface approximative : taille pixel × ~100m²/pixel (résolution Sentinel 10m)
        surface_m2 = region.get('size_pixels', 10) * 100

        ndbi_t1_val = ndbi_values.get('ndbi_t1', 0.0)
        alert_level = classification['alert_level']

        detection = DetectionConstruction.objects.create(
            zone_cadastrale=zone,
            geometry_geojson=region.get('geometry_geojson', '{}'),
            ndbi_t1=ndbi_t1_val,
            ndbi_t2=ndbi_values.get('ndbi_t2', 0.0),
            bsi_value=ndbi_values.get('bsi'),
            surface_m2=surface_m2,
            confidence=classification.get('confidence', 0.5),
            present_in_microsoft=False,
            present_in_t1_sentinel=(ndbi_t1_val > 0.2),
            status=classification['status'],
            alert_level=alert_level,
            verification_required=(alert_level in ['rouge', 'orange']),
        )

        self.logger.info(
            f"Détection #{detection.id} créée : {classification['status']} "
            f"({alert_level}) — Zone: {classification.get('zone_name', 'N/A')}"
        )
        return detection


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def verify_single_detection(
    geometry_geojson: str,
    ndbi_t1: float,
    ndbi_t2: float,
    bsi_val: float = None,
) -> Optional[Dict]:
    """Vérifie une détection unique via l'entonnoir 4 couches."""
    verifier = Verification4Couches()
    return verifier.verify_detection(geometry_geojson, ndbi_t1, ndbi_t2, bsi_val)


def classify_by_zoning_simple(geometry_geojson: str) -> Dict:
    """Classification simple par zonage (pour tests unitaires)."""
    verifier = Verification4Couches()
    return verifier._classify_by_zoning(geometry_geojson, 'new_construction', None)
