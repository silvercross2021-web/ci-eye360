"""
Logique de vérification en 4 couches pour le Module 1 Urbanisme
Pipeline de détection et classification des constructions

Couche 1: Google Open Buildings V3 (vérité terrain, mai 2023, 50cm)
         Remplacement de Microsoft Footprints (données 2020, obsolètes)
Couche 2: Sentinel T1 (référence 2024)
Couche 3: Sentinel T2 (détection 2025)
Couche 4: Cadastre V10 (classification)

CORRECTIFS APPLIQUÉS:
  - A1: Couche 1 utilise ST_DWithin PostGIS 15m autour du centroïde
  - A2: Couche 4 utilise Shapely pour intersection spatiale réelle
  - A3: alert_level = 'veille' (conforme aux ALERT_LEVEL_CHOICES du modèle)
  - H8: Remplacement Microsoft → Google Open Buildings V3 (7 cas de logique)
  - H8: Rejet automatique des détections < 200m² (sous seuil Sentinel-2 10m/pixel)

AMÉLIORATIONS APPORTÉES :
  - L1: Support du type 'demolition' — bâtiments rasés détectés par delta NDBI négatif
"""

import json
import logging
from typing import Dict, List, Optional

from django.db.models import Q
from django.contrib.gis.geos import GEOSGeometry  # ← NOUVEAU POUR POSTGIS
from module1_urbanisme.models import ZoneCadastrale, MicrosoftFootprint, DetectionConstruction
from module1_urbanisme.pipeline.google_v1_client import GoogleV1Client

logger = logging.getLogger(__name__)

# SPATIAL_TOLERANCE supprimé car inutilisé (BUG-015)

# Rayon ST_DWithin pour Google Open Buildings (15m = 10m résolution + 5m marge GPS)
GOOGLE_SEARCH_RADIUS_M = 15

# Surface minimale détectable par Sentinel-2 (2 pixels à 10m = 200m²)
MIN_SURFACE_M2 = 200

# BUG#9 : zones inondables et portuaires = variations naturelles, pas du terrassement (CIV-13)
ZONES_EXCLUES_SOIL = ('flood_prone', 'harbour', 'water', 'airport')


class Verification4Couches:
    """Implémentation de la logique de vérification en 4 couches."""

    def __init__(self):
        self.logger = logger
        self.google_v1 = GoogleV1Client()

    def verify_detection(
        self,
        geometry_geojson: str,
        ndbi_t1_val: float,
        ndbi_t2_val: float,
        bsi_val: Optional[float] = None,
        change_type: str = 'new_construction',
        confidence_ia: float = 0.5,
        surface_m2: float = 0.0,
    ) -> Optional[Dict]:
        """
        Pipeline complet de vérification en 4 couches.

        Args:
            geometry_geojson: Géométrie de la détection en GeoJSON (WGS84)
            ndbi_t1_val:      Valeur NDBI période T1
            ndbi_t2_val:      Valeur NDBI période T2
            bsi_val:          Valeur BSI (optionnel)
            change_type:      'new_construction' | 'soil_activity' | 'demolition'
            confidence_ia:    Score de confiance de l'IA
            surface_m2:       Surface estimée en m²

        Returns:
            Dict avec classification et détails, ou None si filtré.
        """
        try:
            # ── CAS 1 : Rejet automatique détections < 200m² (H8) ────────
            # Sentinel-2 = 10m/pixel → en dessous de 200m², c'est du bruit
            if surface_m2 > 0 and surface_m2 < MIN_SURFACE_M2:
                self.logger.info(
                    f"❌ CAS 1 : Rejet automatique (surface={surface_m2:.0f}m² < {MIN_SURFACE_M2}m²)"
                )
                return None

            # ── Couche 1 : Vérification Google Open Buildings V3 (H8) ───
            # Remplace Microsoft Footprints (données 2020 obsolètes)
            google_result = self._check_google_buildings(geometry_geojson)
            present_in_buildings = google_result["found"]
            google_confidence = google_result["confidence"]
            google_case = google_result["case"]

            # Appliquer les ajustements de confiance selon les 7 cas Google
            confidence_adjustment = google_result["confidence_adjustment"]
            confidence_ia = max(0.0, min(1.0, confidence_ia + confidence_adjustment))

            # CAS 4 : Bâtiment certain pré-existant → filtrer si on cherche une nouvelle construction
            # Mais seulement si le bâtiment était déjà "vu" par Sentinel en T1 (NDBI_T1 élevé)
            if google_case == "FAUX_POSITIF_PRE_EXISTANT" and change_type == 'new_construction':
                if ndbi_t1_val > 0.15: # Bâtiment déjà présent au NDBI en 2024
                    self.logger.info(
                        f"❌ Couche 1 CAS 4 : Bâtiment Google V3 >= 0.75 ET NDBI_T1={ndbi_t1_val:.2f} → REJET (Déjà là)"
                    )
                    return None
                else:
                    # Cas d'une extension ou d'un bâtiment May 2023 non résolu par Sentinel en 2024
                    self.logger.info(
                        f"ℹ️ Couche 1 : Bâtiment Google V3 mais NDBI_T1 faible ({ndbi_t1_val:.2f}) → Modification suspectée"
                    )

            # CAS 3 : Pas de bâtiment Google + NDBI/BSI incohérents
            if google_case == "FAUX_POSITIF_INCOHERENT":
                self.logger.info(
                    f"❌ Couche 1 CAS 3 : 0 bâtiment Google + NDBI/BSI incohérents → FAUX POSITIF"
                )
                return None

            # Si bâtiment connu et détecté comme nouvelle construction → laisser au zonage
            # le soin de reclasser en "Modification" (permet de garder les seuils spectraux bâti)
            # if present_in_buildings and change_type == 'new_construction' and google_confidence >= 0.75:
            #     self.logger.info(
            #         f"ℹ️ Couche 1 : Bâtiment Google V3 (conf={google_confidence:.2f}) → reclassification"
            #     )
            #     change_type = 'soil_activity'

            # ── Couche 2 : Vérification Sentinel T1 ────────────────────
            t1_limit = 0.2 if confidence_ia < 0.8 else 0.50
            if change_type == 'new_construction' and ndbi_t1_val > t1_limit:
                self.logger.info(f"❌ Couche 2 : Filtré (NDBI_T1={ndbi_t1_val:.3f} > {t1_limit})")
                return None

            # ── Couche 3 : Validation cohérence du changement ────────────
            if not self._is_valid_change(ndbi_t1_val, ndbi_t2_val, change_type, confidence_ia):
                self.logger.info(
                    f"⚠️ Couche 3 : Filtré (Incohérence {change_type} "
                    f"T1={ndbi_t1_val:.2f} T2={ndbi_t2_val:.2f} IA={confidence_ia:.2f})"
                )
                return None

            self.logger.info(f"✅ Couche 3 : Détection {change_type} validée !")

            # ── Couche 4 : Classification cadastrale ─────────────────
            classification = self._classify_by_zoning(
                geometry_geojson, change_type, bsi_val, present_in_buildings
            )
            if classification:
                classification['confidence'] = round(
                    0.5 * classification.get('confidence', 0.5) + 0.5 * confidence_ia, 2
                )
                classification['present_microsoft'] = present_in_buildings
                classification['google_case'] = google_case
                classification['verification_required'] = google_result.get(
                    'verification_required', False
                )

                # ── Couche 5 : Arbitrage Temporel V1 (Expert P4) ────────────
                # Si alerte critique et pas de bâtiment V3 → demander à la V1
                # Évite les erreurs sur les bâtiments construits entre 2016 et 2023
                # mais ratés par la segmentation V3.
                if classification['alert_level'] == 'rouge' and not present_in_buildings:
                    self.logger.info(f"⚖️ Tribunal V1 : Interrogation historique (GEE) pour alerte rouge...")
                    coords = self._get_centroid(geometry_geojson)
                    v1_res = self.google_v1.check_presence(coords['lon'], coords['lat'], "2024-02-15")
                    
                    if v1_res['found']:
                        self.logger.info(
                            f"Verdict V1 : Pas une infraction (Déjà là en {v1_res['date_snapshot']}) → Déclassement"
                        )
                        classification['status'] = 'conforme'
                        classification['alert_level'] = 'vert'
                        classification['message'] = (
                            f"Bâtiment historiquement présent (V1 {v1_res['date_snapshot']}) - "
                            f"confirmé par Google Earth Engine. Alerte rouge annulée par arbitrage V1."
                        )
                    else:
                        self.logger.info(f"⚖️ Verdict V1 : Zone vide confirmée → Maintien Alerte Rouge")

            return classification

        except Exception as e:
            self.logger.error(f"Erreur vérification 4 couches: {str(e)}", exc_info=True)
            return None

    def _check_google_buildings(self, geometry_geojson: str) -> Dict:
        """
        Couche 1 (H8) : Vérification Google Open Buildings V3.
        
        Utilise ST_DWithin PostGIS avec rayon 15m autour du centroïde
        (10m résolution Sentinel-2 + 5m marge GPS).
        
        Implémente les 7 cas de logique définis dans le plan d'action H8.
        
        Returns:
            Dict avec clés: found, confidence, case, confidence_adjustment, verification_required
        """
        default = {
            "found": False, "confidence": 0.0, "case": "UNKNOWN",
            "confidence_adjustment": 0.0, "verification_required": True,
        }
        
        try:
            candidate_geom = GEOSGeometry(geometry_geojson)
            centroid = candidate_geom.centroid
            
            # ST_DWithin 15m autour du centroïde (PostGIS)
            # Correction géodésique pour latitude Abidjan (5.3°N)
            # 1 degré latitude ≈ 110580m, 1 degré longitude ≈ 110850m
            # On utilise une moyenne conservatrice pour le rayon
            radius_degrees = GOOGLE_SEARCH_RADIUS_M / 110850.0  # ~0.000135°
            
            nearby_buildings = (
                MicrosoftFootprint.objects
                .filter(geometry__dwithin=(centroid, radius_degrees))
                .order_by('-confidence_score')  # PRIORITÉ AU BÂTIMENT LE PLUS FIABLE (BUG#21)
            )
            
            if not nearby_buildings.exists():
                # CAS 2 ou CAS 3 : aucun bâtiment Google trouvé
                return {
                    "found": False,
                    "confidence": 0.0,
                    "case": "NOUVELLE_CONSTRUCTION_POSSIBLE",
                    "confidence_adjustment": 0.0,  # pas de bonus ni malus
                    "verification_required": True,
                }
            
            # Trouver le bâtiment le plus proche du centroïde
            closest = None
            closest_distance = float('inf')
            for building in nearby_buildings:
                if building.geometry:
                    dist = centroid.distance(building.geometry.centroid)
                    if dist < closest_distance:
                        closest_distance = dist
                        closest = building
            
            if closest is None:
                return default
            
            google_conf = closest.confidence_score or 0.0
            
            # CAS 7 : Google V3 entre 0.65 et 0.70 (structure très incertaine)
            if google_conf < 0.70:
                return {
                    "found": True,
                    "confidence": google_conf,
                    "case": "SURVEILLANCE_PREVENTIVE",
                    "confidence_adjustment": -0.05,
                    "verification_required": True,
                }
            
            # CAS 6 : Google V3 entre 0.70 et 0.75 (probable mais pas certain)
            if google_conf < 0.75:
                return {
                    "found": True,
                    "confidence": google_conf,
                    "case": "EXISTENCE_DOUTEUSE",
                    "confidence_adjustment": -0.10,
                    "verification_required": True,
                }
            
            # CAS 4 ou 5 : Google V3 >= 0.75 (bâtiment certain)
            # Pour le CAS 4 vs 5, il faudrait vérifier Temporal 2023
            # (pas encore implémenté → on suppose pré-existant par défaut)
            return {
                "found": True,
                "confidence": google_conf,
                "case": "FAUX_POSITIF_PRE_EXISTANT",
                "confidence_adjustment": -0.35,
                "verification_required": False,
            }
            
        except Exception as e:
            self.logger.error(f"Couche 1 — Erreur PostGIS Google Buildings: {str(e)}")
            return default

    def _is_in_microsoft_footprints(self, geometry_geojson: str) -> bool:
        """
        COMPAT : Ancien nom conservé pour rétro-compatibilité.
        Utilise désormais _check_google_buildings() en interne.
        """
        result = self._check_google_buildings(geometry_geojson)
        return result["found"]

    # ─────────────────────────────────────────────────────────────────────
    # COUCHE 2/3 — Validation du changement spectral
    # ─────────────────────────────────────────────────────────────────────
    def _is_valid_change(self, ndbi_t1: float, ndbi_t2: float, change_type: str, confidence_ia: float = 0.5) -> bool:
        """
        Couche 3 : Vérifie la cohérence du changement spectral détecté.
        PRINCIPE de la Phase 12 : On fait confiance à l'IA (TinyCD) avant tout.
        """
        try:
            if change_type == 'new_construction':
                # B7 CORRIGÉ : Seuils calibrés pour l'urbanisme ivoirien
                # Tôle ondulée + béton CIV : NDBI ≈ 0.10-0.30 (vs 0.35-0.55 en Europe)
                if confidence_ia >= 0.6:
                    # Seuil adapté CIV : NDBI_T2 > 0.10 (pas 0.05 qui inclut les routes)
                    return ndbi_t2 > 0.10 and ndbi_t1 < 0.45
                
                # Si l'IA est hésitante, on redevient strict
                return ndbi_t2 > 0.15 and ndbi_t1 <= 0.25

            elif change_type == 'soil_activity':
                # Terrassement : NDBI modéré
                return ndbi_t2 <= 0.2

            elif change_type == 'demolition':
                # Éviter le bruit de saisonnalité tout en permettant les vraies démolitions
                # Le bâti d'Abidjan a souvent un NDBI de 0.10. 
                # On valide si le NDBI initial était > 0.10 ET qu'il a nettement chuté (T2 < 0.05)
                # OU si la chute nette (T1 - T2) est supérieure à 0.10
                drop_significant = (ndbi_t1 - ndbi_t2) >= 0.08
                is_building_initially = ndbi_t1 >= 0.10
                is_cleared = ndbi_t2 <= 0.05
                
                return (is_building_initially and is_cleared) or drop_significant

            return False

        except Exception as e:
            self.logger.error(f"Couche 3 — Erreur validation: {str(e)}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # COUCHE 4 — Classification cadastrale
    # CORRECTIF A2 : intersection spatiale réelle via Shapely
    # ─────────────────────────────────────────────────────────────────────
    def _classify_by_zoning(
        self, geometry_geojson: str, change_type: str, bsi_val: Optional[float], present_microsoft: bool = False
    ) -> Dict:
        """
        Couche 4 : Classification selon le zonage cadastral V10.
        OPTIMISATION POSTGIS : Intersection native avec tri par surface de chevauchement.
        """
        try:
            candidate_geom = GEOSGeometry(geometry_geojson)
            centroid = candidate_geom.centroid

            # 1. Chercher d'abord la zone qui contient le centroid (99% des cas)
            matched_zone = ZoneCadastrale.objects.filter(geometry__contains=centroid).first()

            # 2. Si non trouvé (bordure), chercher la zone avec la plus grande intersection
            if not matched_zone:
                zones = ZoneCadastrale.objects.filter(geometry__intersects=candidate_geom)
                best_area = 0
                for zone in zones:
                    overlap_area = zone.geometry.intersection(candidate_geom).area
                    if overlap_area > best_area:
                        best_area = overlap_area
                        matched_zone = zone

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
                return self._classify_new_construction(matched_zone, present_microsoft)
            elif change_type == 'soil_activity':
                return self._classify_soil_activity(matched_zone)
            elif change_type == 'demolition':    # L1 — NOUVEAU
                return self._classify_demolition(matched_zone, present_microsoft)
            else:
                return self._classify_default(matched_zone)

        except Exception as e:
            self.logger.error(f"Couche 4 — Erreur classification PostGIS: {str(e)}", exc_info=True)
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': 'Erreur de classification géographique — inspection recommandée',
                'confidence': 0.3,
            }

    def _classify_new_construction(self, zone: ZoneCadastrale, present_microsoft: bool = False) -> Dict:
        """Classification pour nouvelle construction (3 cas logiques)."""
        zone_status = zone.buildable_status
        
        type_str = "Modification/Extension de bâtiment existant" if present_microsoft else "Nouvelle construction"
        prefix = "MODIFICATION" if present_microsoft else "NOUVELLE"

        # CAS 1 — INFRACTION AU ZONAGE (Alerte Rouge)
        if zone_status == 'forbidden':
            return {
                'status': 'infraction_zonage',
                'alert_level': 'rouge',
                'message': (
                    f"{type_str} détectée en Zone Interdite ({zone.name}). "
                    f"Le plan de zonage V10 interdit toute modification dans cette zone. "
                    f"Transmission recommandée à l'agent cadastral pour vérification terrain."
                ),
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'confidence': 0.95 if present_microsoft else 0.9,
            }

        # CAS 2 — CONSTRUCTION SOUS CONDITION (Alerte Orange)
        elif zone_status == 'conditional':
            return {
                'status': 'sous_condition',
                'alert_level': 'orange',
                'message': (
                    f"{type_str} détectée en Zone Sous Condition ({zone.name}). "
                    f"Vérification du respect des servitudes de sécurité et d'urbanisme requise."
                ),
                'zone_id': zone.zone_id,
                'zone_name': zone.name,
                'zone_type': zone.zone_type,
                'confidence': 0.85 if present_microsoft else 0.8,
            }

        # CAS 3 — DÉVELOPPEMENT CONFORME OU EXTENSION
        elif zone_status == 'buildable':
            if present_microsoft:
                return {
                    'status': 'sous_condition',
                    'alert_level': 'orange',
                    'message': (
                        f"Extension ou surélévation détectée sur bâtiment existant ({zone.name}). "
                        f"Même en Zone Constructible, une modification structurelle majeure "
                        f"nécessite la validation d'un nouveau permis de construire."
                    ),
                    'zone_id': zone.zone_id,
                    'zone_name': zone.name,
                    'zone_type': zone.zone_type,
                    'confidence': 0.8,
                }
            else:
                return {
                    'status': 'conforme',
                    'alert_level': 'vert',
                    'message': (
                        f"Nouvelle construction détectée en Zone Constructible ({zone.name}). "
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
        BUG#9 CORRIGÉ : ignorer les zones inondables et portuaires (faux positifs lagune/berge)
        """
        zone_status = zone.buildable_status
        
        # BUG#9 : zones inondables et portuaires = variations naturelles, pas du terrassement
        if zone.zone_type in ZONES_EXCLUES_SOIL:
            self.logger.info(
                f"⚠️ zone_type={zone.zone_type} → faux positif ignoré (berge/lagune/port)"
            )
            return None
        
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

    def _classify_demolition(self, zone: ZoneCadastrale, present_microsoft: bool = False) -> Dict:
        """
        Classification pour bâtiment rasé/démoli (L1 — NOUVEAU).

        NDBI T1 > 0.25 ET NDBI T2 < 0.05 → structure disparue entre 2024 et 2025.
        Alerte orange : inspection terrain requise pour confirmer la démolition
        et vérifier l'absence de construction de remplacement non déclarée.
        """
        conf = 0.9 if present_microsoft else 0.6
        prefix = "DÉMOLITION CONFIRMÉE" if present_microsoft else "CHANGEMENT DE TERRAIN"
        
        return {
            'status': 'sous_condition',
            'alert_level': 'orange',
            'message': (
                f"{prefix} détecté(e) dans {zone.name} ({zone.zone_type}). "
                f"NDBI T1 élevé ({'Microsoft confirme un bâtiment' if present_microsoft else 'Sentinel détecte un bâtiment'}) en 2024. "
                f"NDBI T2 très bas -> structure absente en 2025. "
                f"Vérification terrain pour confirmer et s'assurer de l'absence de reconstruction non déclarée."
            ),
            'zone_id': zone.zone_id,
            'zone_name': zone.name,
            'zone_type': zone.zone_type,
            'confidence': conf,
        }

    def _get_centroid(self, geometry_geojson: str) -> Dict[str, float]:
        """Calcul robuste du centroïde WGS84 via GEOS."""
        try:
            geom = GEOSGeometry(geometry_geojson)
            centroid = geom.centroid
            return {'lon': centroid.x, 'lat': centroid.y}
        except Exception as e:
            self.logger.error(f"Erreur calcul centroïde: {e}")
            return {'lon': 0, 'lat': 0}


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

                # H8 : Surface estimée pour rejet < 200m²
                surface_m2 = region.get('size_pixels', 0) * 100  # 10m/pixel → 100m²/pixel

                classification = self.verifier.verify_detection(
                    geometry_geojson=region.get('geometry_geojson', '{}'),
                    ndbi_t1_val=ndbi_values.get('ndbi_t1', 0.0),
                    ndbi_t2_val=ndbi_values.get('ndbi_t2', 0.0),
                    bsi_val=ndbi_values.get('bsi'),
                    change_type=region.get('change_type', 'new_construction'),
                    confidence_ia=region.get('confidence', 0.5),
                    surface_m2=surface_m2,
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
            geometry=GEOSGeometry(region.get('geometry_geojson', '{}')),
            ndbi_t1=ndbi_t1_val,
            ndbi_t2=ndbi_values.get('ndbi_t2', 0.0),
            bsi_value=ndbi_values.get('bsi'),
            surface_m2=surface_m2,
            confidence=classification.get('confidence', 0.5),
            present_in_microsoft=classification.get('present_microsoft', False),
            present_in_t1_sentinel=(ndbi_t1_val > 0.2),
            status=classification['status'],
            alert_level=alert_level,
            verification_required=classification.get(
                'verification_required', alert_level in ['rouge', 'orange']
            ),
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
    bsi_val: Optional[float] = None,
) -> Optional[Dict]:
    """Vérifie une détection unique via l'entonnoir 4 couches."""
    verifier = Verification4Couches()
    return verifier.verify_detection(geometry_geojson, ndbi_t1, ndbi_t2, bsi_val)


def classify_by_zoning_simple(geometry_geojson: str) -> Dict:
    """Classification simple par zonage (pour tests unitaires)."""
    verifier = Verification4Couches()
    return verifier._classify_by_zoning(geometry_geojson, 'new_construction', None)
