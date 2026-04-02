"""
Management command pour exécuter le pipeline complet de détection NDBI + vérification 4 couches.

CORRECTIFS APPLIQUÉS:
  - A6 : Les géométries sont converties de coordonnées pixel → WGS84 (longitude/latitude)
         via le transform affine du raster Sentinel-2.
         L'ancienne implémentation créait des polygones en coordonnées pixel invalides.

AMÉLIORATIONS APPORTÉES :
  - L1 : Extraction des régions démolies (change_type='demolition')
  - L3 : Calcul NDVI T2 + passage à detect_changes() pour masquer la végétation
  - L5 : Score de confiance dynamique via compute_confidence()
  - L6 : Utilisation du fichier SCL pour masquer les pixels nuageux
"""

import os
import sys

# Configuration GDAL pour Windows (via PostgreSQL 16)
if os.name == 'nt':
    POSTGRES_BIN = r"C:\Program Files\PostgreSQL\16\bin"
    os.environ['PATH'] = POSTGRES_BIN + os.pathsep + os.environ.get('PATH', '')
    os.environ['GDAL_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgdal-34.dll')
    os.environ['GEOS_LIBRARY_PATH'] = os.path.join(POSTGRES_BIN, 'libgeos_c.dll')

import json
import logging
from datetime import date, datetime, timedelta

import numpy as np
import rasterio
import rasterio.transform as rtransform

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone

from module1_urbanisme.models import ImageSatellite, DetectionConstruction
from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator
from module1_urbanisme.pipeline.verification_4_couches import DetectionPipeline
from module1_urbanisme.pipeline.api_health_checker import APIHealthChecker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# B37 : Résolution Sentinel-2 par défaut (fallback si transform affine indisponible)
# 10m / (111 000 m/deg × cos(5.3°)) ≈ 0.0000904 degrés à la latitude d'Abidjan
# Préférer ndbi_results["transform"] quand disponible pour la taille pixel réelle.
PIXEL_SIZE_DEGREES = 0.00009


class Command(BaseCommand):
    help = "Exécute le pipeline complet de détection NDBI + vérification 4 couches"

    def add_arguments(self, parser):
        parser.add_argument("--date-t1", type=str, help="Date image T1 (YYYY-MM-DD)")
        parser.add_argument("--date-t2", type=str, help="Date image T2 (YYYY-MM-DD)")
        parser.add_argument(
            "--threshold-built", type=float, default=0.2,
            help="Seuil NDBI pour surfaces bâties (défaut: 0.2)"
        )
        parser.add_argument(
            "--threshold-soil", type=float, default=0.15,
            help="Seuil BSI pour sol nu (défaut: 0.15)"
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les résultats sans écrire en base"
        )
        parser.add_argument(
            "--min-region-size", type=int, default=2,
            help="Taille minimale en pixels pour une région (défaut: 2 ≈ 200m² à 10m/pixel Sentinel-2)"
        )
        parser.add_argument(
            "--use-ai", action="store_true",
            help="Utiliser le modèle de Machine Learning IA au lieu du seuillage NDBI empirique"
        )
        parser.add_argument(
            "--use-sar", action="store_true",
            help="Activer la détection Anti-Nuage par ondes Radar Sentinel-1 (SAR)"
        )
        parser.add_argument(
            "--use-hf-ai", action="store_true",
            help="Valider les candidats via l'IA cloud HuggingFace (HUGGINGFACE_TOKEN dans .env, zéro installation)"
        )
        parser.add_argument(
            "--use-tinycd", action="store_true",
            help="[EXPÉRIMENTAL] TinyCD deep learning — poids non adaptés au contexte africain Sentinel-2. Préférer NDBI ou --use-ai (K-Means)"
        )
        parser.add_argument(
            "--download-b03", action="store_true",
            help="Télécharger automatiquement B03 (Green) via CDSE pour activer le masque NDWI eau/lagunaire"
        )
        parser.add_argument(
            "--clear-previous", action="store_true",
            help="M13: Supprimer les détections existantes pour la même paire T1/T2 avant de relancer"
        )
        parser.add_argument(
            "--n-clusters", type=int, default=4,
            help="B38: Nombre de clusters K-Means (défaut: 4). Ajuster selon complexité spectrale de la zone."
        )

    def handle(self, *args, **options):
        date_t1 = options.get("date_t1")
        date_t2 = options.get("date_t2")
        threshold_built = options["threshold_built"]
        threshold_soil = options["threshold_soil"]
        dry_run = options["dry_run"]
        min_region_size = options["min_region_size"]
        use_ai = options["use_ai"]
        use_tinycd = options.get("use_tinycd", False)
        use_sar = options.get("use_sar", False)
        use_hf_ai = options.get("use_hf_ai", False)
        download_b03 = options.get("download_b03", False)
        clear_previous = options.get("clear_previous", False)
        self._n_clusters = options.get("n_clusters", 4)

        # ══ DIAGNOSTIC DE TOUTES LES APIS AU DÉMARRAGE ═══════════════════
        checker = APIHealthChecker()
        checker.run_all_checks()  # Affiche l'état complet dans les logs
        checker.assert_minimum_viable()  # Bloque si aucune source de données dispo

        # ══ M23 : WARNING TINYCD SANS B03 ═════════════════════════
        if use_tinycd and not download_b03:
            self.stdout.write(self.style.WARNING(
                "⚠️  TinyCD nécessite B03 (Green) pour des résultats fiables. "
                "Ajoutez --download-b03 ou les résultats seront dégradés (fallback B04/B08/B11)."
            ))

        self.stdout.write("🚀 LANCEMENT PIPELINE DE DÉTECTION CIV-EYE MODULE 1")
        self.stdout.write(f"📅 Période    : {date_t1 or 'auto'} → {date_t2 or 'auto'}")
        
        if use_tinycd:
            mode_text = "[MODE EXPÉRIMENTAL 🧠 TinyCD — poids non adaptés au contexte africain]"
        elif use_ai:
            mode_text = "[MODE ML CLASSIQUE 🤖 K-Means Clustering]"
        else:
            mode_text = f"[MODE NDBI EMPIRIQUE 🔢] Seuils: Bâti={threshold_built}, Sol={threshold_soil}"
            
        self.stdout.write(f"🎯 Moteur     : {mode_text}")
        self.stdout.write(f"🔬 Min pixels : {min_region_size}")
        if dry_run:
            self.stdout.write("⚠️  MODE DRY-RUN — aucune écriture en base\n")
        try:
            # ── Étape 1 : Récupération des images ────────────────────
            image_t1, image_t2 = self.get_sentinel_images(date_t1, date_t2)

            # ══ TÉLÉCHARGEMENT B03 VIA CDSE SI DEMANDÉ ══════════════════════
            if download_b03:
                from module1_urbanisme.pipeline.b03_downloader import download_b03_cdse
                from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
                self.stdout.write("📡 Téléchargement B03 automatique (NDWI/masque eau)...")
                d1 = str(image_t1.date_acquisition)
                d2 = str(image_t2.date_acquisition)
                for date_str, img in [(d1, image_t1), (d2, image_t2)]:
                    date_to = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d")
                    b03_path = download_b03_cdse(date_str, date_to)
                    if b03_path:
                        self.stdout.write(f"   ✅ B03 réel ({date_str}) : {b03_path}")
                    else:
                        # Fallback synthèse B03 = 0.75×B04 + 0.25×B08 (Delegido 2011)
                        b03_synth = synthesize_b03(img.bands["B04"], img.bands["B08"])
                        if b03_synth:
                            self.stdout.write(f"   🔧 B03 synthétisé ({date_str}) : {b03_synth}")
                        else:
                            self.stdout.write(self.style.WARNING(
                                f"   ⚠️  B03 indisponible ({date_str}) — masque eau proxy activé"
                            ))

            # M13 : Suppression des détections précédentes pour cette paire T1/T2
            if clear_previous and not dry_run:
                from module1_urbanisme.models import DetectionConstruction
                deleted_count = DetectionConstruction.objects.filter(
                    date_detection__gte=image_t1.date_acquisition,
                ).delete()[0]
                self.stdout.write(self.style.WARNING(
                    f"⚠️  {deleted_count} détections précédentes supprimées"
                ))

            # M11 : Validation intervalle T1-T2 (3-18 mois recommandé)
            delta = (image_t2.date_acquisition - image_t1.date_acquisition).days
            if delta < 90:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Intervalle T1-T2 = {delta} jours (< 3 mois). "
                    f"Risque de changements non détectables."
                ))
            elif delta > 540:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Intervalle T1-T2 = {delta} jours (> 18 mois). "
                    f"Risque de faux positifs par changements saisonniers cumulés."
                ))

            # B36 : Vérification saison sèche vs saison des pluies
            # Abidjan saison sèche = Nov-Mars, saison des pluies = Avr-Oct
            m1 = image_t1.date_acquisition.month
            m2 = image_t2.date_acquisition.month
            dry_months = {11, 12, 1, 2, 3}
            t1_dry = m1 in dry_months
            t2_dry = m2 in dry_months
            if t1_dry != t2_dry:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  B36 : T1 ({'sèche' if t1_dry else 'pluies'}) vs "
                    f"T2 ({'sèche' if t2_dry else 'pluies'}) — saisons différentes. "
                    f"Risque de faux positifs par changement saisonnier de végétation."
                ))

            # ── Étape 2 : Inférence IA / Calcul Changements ─────────────────
            if use_tinycd:
                self.stdout.write("\n🤖 Étape 1A : Éclaireur K-Means (Cartographie globale sols & contexte)...")
                # 1. K-Means pour le contexte spectral global (sol nu, NDBI, etc.)
                ndbi_results = self.calculate_ai_pipeline(image_t1, image_t2)

                self.stdout.write("🧠 Étape 1B : Inférence Deep Learning (PyTorch TinyCD) pour les Bâtiments...")
                from module1_urbanisme.pipeline.deep_learning_detector import DeepLearningDetector
                from module1_urbanisme.pipeline.b03_downloader import calculate_ndwi_from_paths
                import numpy as np
                import rasterio
                dl_detector = DeepLearningDetector()
                # P9 CORRIGÉ : erreur explicite si poids absents (au lieu de silence)
                if not dl_detector.is_ready:
                    raise CommandError(
                        "❌ [TinyCD] model_weights.pth introuvable dans data_use/weights/\n"
                        "   Télécharger levir_best.pth depuis :\n"
                        "   https://github.com/AndreaCodegoni/Tiny_model_4_CD/tree/main/pretrained_models\n"
                        "   → Renommer en 'model_weights.pth' dans module1_urbanisme/data_use/weights/"
                    )
                
                # ── B1 CORRIGÉ : TinyCD avec vraies bandes RGB si B03 disponible ──
                # TinyCD a été entraîné sur B04(R)/B03(G)/B02(B), pas sur IRR.
                # On charge B03 si présent (téléchargé via --download-b03)
                def find_b03(date_str):
                    """Cherche B03 dans sentinel_api_exports/{date_str}/ ou sentinel/"""
                    import os
                    from django.conf import settings
                    base = os.path.join(settings.BASE_DIR, "module1_urbanisme", "data_use")
                    candidates = [
                        os.path.join(base, "sentinel_api_exports", date_str, f"B03_{date_str}.tif"),
                        os.path.join(base, "sentinel_api_exports", date_str, f"B03_{date_str}.tiff"),
                        os.path.join(base, "sentinel", f"{date_str[:7]}_Sentinel-2_L2A_B03.tiff"),
                    ]
                    return next((p for p in candidates if os.path.exists(p)), None)

                b03_t1 = find_b03(str(image_t1.date_acquisition))
                b03_t2 = find_b03(str(image_t2.date_acquisition))
                
                # Fallback : B03 synthétique si B03 réelle non disponible
                if b03_t1 is None:
                    try:
                        from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
                        b03_t1 = synthesize_b03(image_t1.bands["B04"], image_t1.bands["B08"])
                        self.stdout.write("   🔧 B03 T1 synthétisé (fallback Delegido 2011)")
                    except Exception as e:
                        self.stdout.write(f"   ⚠️  Synthèse B03 T1 impossible : {e}")
                
                if b03_t2 is None:
                    try:
                        from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
                        b03_t2 = synthesize_b03(image_t2.bands["B04"], image_t2.bands["B08"])
                        self.stdout.write("   🔧 B03 T2 synthétisé (fallback Delegido 2011)")
                    except Exception as e:
                        self.stdout.write(f"   ⚠️  Synthèse B03 T2 impossible : {e}")

                has_b03 = b03_t1 is not None and b03_t2 is not None
                
                def extract_tensor(image_obj, b03_path=None):
                    """Charge B04/B03/B11 (RGB approx) ou B04/B08/B11 selon dispo."""
                    with rasterio.open(image_obj.bands["B04"]) as src: b04 = src.read(1)
                    with rasterio.open(image_obj.bands["B08"]) as src: b08 = src.read(1)
                    with rasterio.open(image_obj.bands["B11"]) as src: b11 = src.read(1)
                    if b03_path:
                        with rasterio.open(b03_path) as src: b03 = src.read(1)
                        # B04=Rouge, B03=Vert, B08=NIR (substitut Bleu manquant)
                        return np.stack([b04, b03, b08], axis=2)
                    else:
                        # Fallback : B04/B08/B11 (spectral, moins bon pour TinyCD)
                        return np.stack([b04, b08, b11], axis=2)

                if has_b03:
                    self.stdout.write("   ✅ B03 (Vert) trouvé → TinyCD en mode RGB réel [B04/B03/B08]")
                else:
                    self.stdout.write("   ⚠️  B03 absent → TinyCD en mode spectral [B04/B08/B11] (moins précis)")
                    self.stdout.write("   💡 Conseil : lancer 'run_detection --download-b03' pour meilleure précision")

                ms_t1 = extract_tensor(image_t1, b03_t1)
                ms_t2 = extract_tensor(image_t2, b03_t2)
                
                # Prédiction par le modèle Deep Learning
                mask_dl = dl_detector.detect(ms_t1, ms_t2)                
                
                # ── B4 + B8 CORRIGÉS : Masque eau renforcé (lagune + ponts/quais) ──
                # NDWI (si B03 dispo) est le meilleur masque eau — capte même les quais humides
                ndwi_mask = None
                if has_b03:
                    from module1_urbanisme.pipeline.b03_downloader import calculate_ndwi_from_paths
                    ndwi_t1 = calculate_ndwi_from_paths(b03_t1, image_t1.bands["B08"])
                    ndwi_t2 = calculate_ndwi_from_paths(b03_t2, image_t2.bands["B08"])
                    if ndwi_t1 is not None and ndwi_t2 is not None:
                        ndwi_mask = (ndwi_t1 > 0.0) | (ndwi_t2 > 0.0)
                        self.stdout.write(f"   🌊 Masque NDWI actif : {ndwi_mask.sum():,} pixels eau exclus")
                
                # Fallback eau : NDBI très négatif (B8 : eau < -0.05, bateaux < 0.10)
                # Valeur durcie à -0.05 au lieu de -0.15 (B8 CORRIGÉ)
                water_proxy = (ndbi_results["ndbi_t1"] < -0.05) | (ndbi_results["ndbi_t2"] < -0.05)
                if ndwi_mask is not None:
                    water_proxy = water_proxy | ndwi_mask
                
                mask_change = (mask_dl > 0) & ~water_proxy
                
                # Si le NDBI a augmenté, c'est une apparition (construction).
                # S'il a baissé, c'est une disparition (démolition).
                is_built = mask_change & (ndbi_results["ndbi_t2"] > ndbi_results["ndbi_t1"])
                is_demo = mask_change & (ndbi_results["ndbi_t1"] >= ndbi_results["ndbi_t2"])
                
                self.stdout.write(f"   [TinyCD] Changements filtrés : {np.sum(mask_change)} px | Construits: {np.sum(is_built)} | Démolis: {np.sum(is_demo)}")
                
                ndbi_results["changes"]["new_constructions"] = is_built
                if "demolished" in ndbi_results["changes"]:
                    ndbi_results["changes"]["demolished"] = ndbi_results["changes"]["demolished"] | is_demo
                else:
                    ndbi_results["changes"]["demolished"] = is_demo
                
                # Méta-données spatiales ajoutées au résultat global
                with rasterio.open(image_t1.bands["B04"]) as src: 
                    ndbi_results["raster_transform"] = src.transform
                    ndbi_results["raster_crs"] = src.crs
                    ndbi_results["bounds"] = src.bounds            # Méta-données spatiales ajoutées au résultat global
            elif use_ai:
                self.stdout.write("\n🤖 Étape 1 : Inférence ML Classique (K-Means)...")
                ndbi_results = self.calculate_ai_pipeline(image_t1, image_t2)
            else:
                self.stdout.write("\n📊 Étape 1 : Calcul NDBI empirique...")
                ndbi_results = self.calculate_ndbi_pipeline(
                    image_t1, image_t2, threshold_built, threshold_soil
                )

            # ── Intégration Phase 7 : Fusion Sentinel-1 SAR ─────────────────
            if use_sar:
                self.stdout.write("\n📡 Étape 1.5 : Acquisition Radar Sentinel-1 (Cloud-Piercing)...")
                try:
                    from module1_urbanisme.pipeline.sentinel1_sar import fetch_and_evaluate_sar_for_bbox, merge_optical_and_sar_masks
                    sar_info = fetch_and_evaluate_sar_for_bbox(None, "TREICHVILLE", date_t1, date_t2)
                    self.stdout.write(f"   ℹ️ {sar_info['message']}")
                    # En cas de donnees SAR reelles, on executerait:
                    # optical_mask = ndbi_results["changes"]["new_constructions"]
                    # ndbi_results["changes"]["new_constructions"] = merge_optical_and_sar_masks(optical_mask, sar_mask)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠️ Erreur module SAR : {e}"))


            # ── Étape 3 : Extraction des régions ─────────────────────────
            self.stdout.write("\n🔍 Étape 2 : Extraction des régions de changement...")
            change_regions = self.extract_change_regions(
                ndbi_results, min_region_size
            )
            self.stdout.write(
                f"   → {sum(1 for r in change_regions if r['change_type']=='new_construction')} "
                f"nouvelles constructions + "
                f"{sum(1 for r in change_regions if r['change_type']=='soil_activity')} terrassements"
            )

            # ══ Étape 2.5 : Validation IA Cloud HuggingFace (optionnel) ══════
            if use_hf_ai:
                self.stdout.write("\n🤖 Étape 2.5 : Validation IA Cloud (HuggingFace API)...")
                try:
                    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
                    hf_client = HuggingFaceAIClient()
                    if hf_client.is_available():
                        change_regions = hf_client.batch_validate(
                            change_regions,
                            ndbi_results["ndbi_t1"],
                            ndbi_results["ndbi_t2"]
                        )
                        self.stdout.write(self.style.SUCCESS(f"   → {len(change_regions)} candidats validés par IA cloud"))
                    else:
                        self.stdout.write(self.style.WARNING("   ⚠️  HuggingFace non disponible — HUGGINGFACE_TOKEN absent dans .env"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠️  Erreur IA cloud : {e} — pipeline K-Means utilisé"))

            # ── Étape 4 : Vérification 4 couches ─────────────────────────
            self.stdout.write("✅ Étape 3 : Vérification 4 couches + classification...")
            if not dry_run:
                detections = self.process_4couches_verification(change_regions, image_t2)
                self.stdout.write(
                    self.style.SUCCESS(f"   → {len(detections)} détections créées en base")
                )
            else:
                self.stdout.write(
                    f"   [DRY-RUN] Créerait {len(change_regions)} détections potentielles"
                )

            # ── Étape 5 : Statistiques ────────────────────────────────────
            self.print_detection_statistics()
            self.stdout.write(self.style.SUCCESS("\n🎉 PIPELINE TERMINÉ AVEC SUCCÈS"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERREUR PIPELINE : {str(e)}"))
            logger.error("Erreur pipeline", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────
    def get_sentinel_images(self, date_t1=None, date_t2=None):
        """Récupère les images Sentinel T1 et T2 depuis la BDD."""
        if not date_t1 or not date_t2:
            images = ImageSatellite.objects.order_by("date_acquisition")
            if images.count() < 2:
                raise ValueError(
                    "Moins de 2 images en base. "
                    "Exécuter d'abord : python manage.py import_sentinel"
                )
            image_t1 = images.first()
            image_t2 = images.last()
        else:
            image_t1 = ImageSatellite.objects.get(date_acquisition=date.fromisoformat(date_t1))
            image_t2 = ImageSatellite.objects.get(date_acquisition=date.fromisoformat(date_t2))

        self.stdout.write(
            f"📷 Images sélectionnées : T1={image_t1.date_acquisition}, T2={image_t2.date_acquisition}"
        )

        # M12 : Vérification couverture géographique T1/T2
        self._verify_geo_coverage(image_t1, image_t2)

        return image_t1, image_t2

    def _verify_geo_coverage(self, image_t1, image_t2):
        """M12 : Vérifie que T1 et T2 couvrent la même zone géographique."""
        try:
            import rasterio
            # Prendre la première bande disponible de chaque image
            band_t1 = next(iter(image_t1.bands.values()))
            band_t2 = next(iter(image_t2.bands.values()))
            with rasterio.open(band_t1) as src1, rasterio.open(band_t2) as src2:
                b1, b2 = src1.bounds, src2.bounds
                # Vérifier chevauchement minimal (80% en surface)
                overlap_left = max(b1.left, b2.left)
                overlap_right = min(b1.right, b2.right)
                overlap_bottom = max(b1.bottom, b2.bottom)
                overlap_top = min(b1.top, b2.top)
                if overlap_right <= overlap_left or overlap_top <= overlap_bottom:
                    self.stdout.write(self.style.ERROR(
                        "❌ M12 : T1 et T2 ne se chevauchent PAS géographiquement !"
                    ))
                    return
                overlap_area = (overlap_right - overlap_left) * (overlap_top - overlap_bottom)
                t1_area = (b1.right - b1.left) * (b1.top - b1.bottom)
                ratio = overlap_area / t1_area if t1_area > 0 else 0
                if ratio < 0.8:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ M12 : Couverture géo T1/T2 = {ratio:.0%} (< 80%). "
                        f"Résultats potentiellement incohérents en bordure."
                    ))
                else:
                    self.stdout.write(f"   ✅ Couverture géo T1/T2 : {ratio:.0%}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️ M12 : Vérification géo impossible : {e}"))

    # ─────────────────────────────────────────────────────────────────────
    def calculate_ai_pipeline(self, image_t1, image_t2):
        from module1_urbanisme.pipeline.ai_detector import AIDetector
        
        ai = AIDetector(n_clusters=self._n_clusters)
        
        # Load T1 arrays
        with rasterio.open(image_t1.bands["B04"]) as src: b04_t1 = src.read(1)
        with rasterio.open(image_t1.bands["B08"]) as src: b08_t1 = src.read(1)
        with rasterio.open(image_t1.bands["B11"]) as src: b11_t1 = src.read(1)

        # Load T2 arrays
        with rasterio.open(image_t2.bands["B04"]) as src: b04_t2 = src.read(1)
        with rasterio.open(image_t2.bands["B08"]) as src: b08_t2 = src.read(1)
        with rasterio.open(image_t2.bands["B11"]) as src:
            b11_t2 = src.read(1)
            raster_transform = src.transform

        # 1. Calcul des indices RÉELS pour le Juge (Validation)
        calc = NDBICalculator()
        ndbi_t1 = calc.calculate_ndbi(image_t1.bands["B08"], image_t1.bands["B11"])
        ndbi_t2 = calc.calculate_ndbi(image_t2.bands["B08"], image_t2.bands["B11"])
        bsi_t2 = calc.calculate_bsi(image_t2.bands["B04"], image_t2.bands["B08"], image_t2.bands["B11"])

        # 2. Inférence K-Means pour la segmentation
        self.stdout.write("   IA: Prédiction Bâtiments T1...")
        mask_t1, _ = ai.predict_buildings(b04_t1, b08_t1, b11_t1)
        
        self.stdout.write("   IA: Prédiction Bâtiments T2...")
        mask_t2, _ = ai.predict_buildings(b04_t2, b08_t2, b11_t2)

        scl_path = str(image_t2.classification_map) if image_t2.classification_map else None
        cloud_pct = 0.0
        if scl_path:
            with rasterio.open(scl_path) as src: scl = src.read(1)
            # Masquer nuages ET EAU (6=Eau, 3=Ombre nuage, 8-10=Nuages)
            # BUG#2 CORRIGÉ : class 6 (eau) ajoutée pour exclure bateaux et lagune
            cloud_mask = (scl == 3) | (scl == 6) | (scl == 8) | (scl == 9) | (scl == 10)
            
            # Appliquer le masque SCL eau aux masques K-Means (pixels → 0)
            mask_t1[cloud_mask] = 0
            mask_t2[cloud_mask] = 0
            
            # CORRECTION COMPLÈTE : appliquer aussi le masque eau aux arrays NDBI bruts
            # Sans ça, les valeurs NDBI des bateaux/lagune polluent l'arbitrage spectral
            # dans verification_4_couches et la logique is_built/is_demo de TinyCD
            ndbi_t1[cloud_mask] = 0.0
            ndbi_t2[cloud_mask] = 0.0
            bsi_t2[cloud_mask] = 0.0
            
            cloud_pct = (np.sum(cloud_mask) / cloud_mask.size) * 100.0

        # ── B4 + B8 CORRIGÉS : Masque eau renforcé dans K-Means ──
        # NDWI (via B03 synthétique) pour capturer ponts/quais/bateaux non couverts par SCL
        ndwi_extra_mask = None
        try:
            from module1_urbanisme.pipeline.b03_synthesizer import synthesize_b03
            from module1_urbanisme.pipeline.b03_downloader import calculate_ndwi_from_paths
            b03_t1_path = synthesize_b03(image_t1.bands["B04"], image_t1.bands["B08"])
            b03_t2_path = synthesize_b03(image_t2.bands["B04"], image_t2.bands["B08"])
            if b03_t1_path and b03_t2_path:
                ndwi_t1 = calculate_ndwi_from_paths(b03_t1_path, image_t1.bands["B08"])
                ndwi_t2 = calculate_ndwi_from_paths(b03_t2_path, image_t2.bands["B08"])
                if ndwi_t1 is not None and ndwi_t2 is not None:
                    ndwi_extra_mask = (ndwi_t1 > 0.0) | (ndwi_t2 > 0.0)
                    self.stdout.write(f"   🌊 Masque NDWI (K-Means) : {ndwi_extra_mask.sum():,} pixels eau/ponts exclus")
        except Exception as e:
            self.stdout.write(f"   ⚠️  Masque NDWI non disponible : {e}")

        # B8 CORRIGÉ : seuil eau durci à -0.05 (capture bateaux en métal NDBI ≈ -0.05 à +0.10)
        water_proxy = (ndbi_t2 < -0.05) | (ndbi_t1 < -0.05)
        if ndwi_extra_mask is not None:
            water_proxy = water_proxy | ndwi_extra_mask

        # Différenciation Machine Learning (uniquement sur pixels non-eau)
        new_constructions = (mask_t2 == 1) & (mask_t1 == 0) & ~water_proxy
        demolished = (mask_t1 == 1) & (mask_t2 == 0) & ~water_proxy
        
        # Récupération de l'activité du sol (terrassement) via BSI
        # BUG#4 CORRIGÉ : on ajoute le masque eau pour exclure la lagune et les berges
        calc.threshold_built = 0.2
        calc.threshold_soil = 0.05
        soil_activity = (bsi_t2 > calc.threshold_soil) & (ndbi_t2 <= calc.threshold_built) & ~water_proxy
        
        # Le format retourné contient maintenant les VRAIS indices pour le Juge
        return {
            "ndbi_t1": ndbi_t1,
            "ndbi_t2": ndbi_t2, 
            "bsi_t2": bsi_t2,
            "cloud_pct": cloud_pct,
            "raster_transform": raster_transform,
            "changes": {
                "new_constructions": new_constructions.astype(np.uint8),
                "soil_activity": soil_activity.astype(np.uint8),
                "demolished": demolished.astype(np.uint8)
            }
        }

    # ─────────────────────────────────────────────────────────────────────
    def calculate_ndbi_pipeline(self, image_t1, image_t2, threshold_built, threshold_soil):
        """Calcule les NDBI T1/T2, le BSI T2, et détecte les changements."""
        calc = NDBICalculator()
        calc.threshold_built = threshold_built
        calc.threshold_soil = threshold_soil

        bands_t1 = image_t1.bands
        bands_t2 = image_t2.bands

        # Vérification des bandes requises
        for band in ("B08", "B11"):
            if band not in bands_t1:
                raise ValueError(f"Bande {band} manquante pour T1 ({image_t1.date_acquisition})")
            if band not in bands_t2:
                raise ValueError(f"Bande {band} manquante pour T2 ({image_t2.date_acquisition})")

        self.stdout.write("   Calcul NDBI T1...")
        ndbi_t1 = calc.calculate_ndbi(bands_t1["B08"], bands_t1["B11"])

        self.stdout.write("   Calcul NDBI T2...")
        ndbi_t2 = calc.calculate_ndbi(bands_t2["B08"], bands_t2["B11"])

        bsi_t2 = None
        if "B04" in bands_t2 and "B08" in bands_t2 and "B11" in bands_t2:
            self.stdout.write("   Calcul BSI T2...")
            bsi_t2 = calc.calculate_bsi(bands_t2["B04"], bands_t2["B08"], bands_t2["B11"])

        # L3 : NDVI T2 pour masque végétation
        ndvi_t2 = None
        if "B04" in bands_t2 and "B08" in bands_t2:
            self.stdout.write("   Calcul NDVI T2 (masque végétation L3)...")
            ndvi_t2 = calc.calculate_ndvi(bands_t2["B04"], bands_t2["B08"])

        # M20 : Calcul BUI (Built-Up Index = NDBI - NDVI) pour filtrer faux positifs végétation
        bui_t2 = None
        if ndvi_t2 is not None and ndbi_t2 is not None:
            self.stdout.write("   Calcul BUI T2 (NDBI - NDVI, filtre végétation M20)...")
            bui_t2 = calc.calculate_bui(ndbi_t2, ndvi_t2)

        # L6 : Masque nuages ET EAU via SCL si disponible
        scl_path = str(image_t2.classification_map) if image_t2.classification_map else None  # chemin absolu stocké en BDD
        if scl_path:
            self.stdout.write(f"   Masque SCL eau+nuages (L6) : {scl_path}...")
            cloud_pct = calc.get_cloud_percentage(scl_path)
            self.stdout.write(f"   → Couverture nuageuse T2 : {cloud_pct:.1f}%")
            # CORRECTION COMPLÈTE : apply_scl_mask maintenant inclut class 6 (Eau)
            # Cela masque la lagune, les bateaux et zones côtières sur TOUS les arrays
            ndbi_t1 = calc.apply_scl_mask(ndbi_t1, scl_path)
            ndbi_t2 = calc.apply_scl_mask(ndbi_t2, scl_path)
            if bsi_t2 is not None:
                bsi_t2 = calc.apply_scl_mask(bsi_t2, scl_path)
            if ndvi_t2 is not None:
                ndvi_t2 = calc.apply_scl_mask(ndvi_t2, scl_path)
        else:
            cloud_pct = 0.0
            self.stdout.write("   ⚠️  Pas de fichier SCL disponible — masque nuages ignoré")

        self.stdout.write("   Détection changements...")
        change_results = calc.detect_changes(ndbi_t1, ndbi_t2, bsi_t2, ndvi_t2=ndvi_t2)

        # Récupérer le transform du raster B08 de T2 pour la conversion pixel→geo
        with rasterio.open(bands_t2["B08"]) as src:
            raster_transform = src.transform

        return {
            "ndbi_t1": ndbi_t1,
            "ndbi_t2": ndbi_t2,
            "bsi_t2": bsi_t2,
            "ndvi_t2": ndvi_t2,          # L3
            "cloud_pct": cloud_pct,      # L5+L6
            "changes": change_results,
            "raster_transform": raster_transform,
        }

    # ─────────────────────────────────────────────────────────────────────
    def extract_change_regions(self, ndbi_results, min_region_size):
        """Extrait les régions et enrichit chaque région avec géométrie WGS84 et valeurs NDBI."""
        calc = NDBICalculator()
        raster_transform = ndbi_results["raster_transform"]
        ndbi_t1 = ndbi_results["ndbi_t1"]
        ndbi_t2 = ndbi_results["ndbi_t2"]
        bsi_t2 = ndbi_results.get("bsi_t2")
        cloud_pct = ndbi_results.get("cloud_pct", 0.0)

        all_regions = []

        def enrich_region(region, change_type):
            """Enrichit un dict région avec géométrie WGS84, NDBI et confiance."""
            region["change_type"] = change_type
            region["geometry_geojson"] = self._pixel_region_to_geojson(region, raster_transform)

            # ─── CORRECTIF #1 (BUG CRITIQUE) ──────────────────────────────
            # AVANT : on lisait NDBI sur 1 seul pixel (centroïde), très sensible au bruit.
            # MAINTENANT : on calcule la MÉDIANE sur toute la bbox de la région.
            # La médiane est robuste aux ombres, artefacts et nuages résiduels.
            min_row, min_col, max_row, max_col = region["bbox"]
            # Clamp pour ne pas dépasser les limites du raster
            max_row = min(max_row + 1, ndbi_t1.shape[0])
            max_col = min(max_col + 1, ndbi_t1.shape[1])

            patch_t1 = ndbi_t1[min_row:max_row, min_col:max_col]
            patch_t2 = ndbi_t2[min_row:max_row, min_col:max_col]

            valid_t1 = patch_t1[~np.isnan(patch_t1)]
            valid_t2 = patch_t2[~np.isnan(patch_t2)]

            ndbi_t1_val = float(np.median(valid_t1)) if len(valid_t1) > 0 else 0.0
            ndbi_t2_val = float(np.median(valid_t2)) if len(valid_t2) > 0 else 0.0

            # BSI : médiane aussi (ou fallback 0)
            if bsi_t2 is not None:
                patch_bsi = bsi_t2[min_row:max_row, min_col:max_col]
                valid_bsi = patch_bsi[~np.isnan(patch_bsi)]
                bsi_val = float(np.median(valid_bsi)) if len(valid_bsi) > 0 else None
            else:
                bsi_val = None

            region["ndbi_t1"] = ndbi_t1_val
            region["ndbi_t2"] = ndbi_t2_val
            region["bsi"]    = bsi_val
            # ─────────────────────────────────────────────────────────────

            # L5 : score de confiance dynamique
            conf = calc.compute_confidence(
                ndbi_t1=ndbi_t1_val,
                ndbi_t2=ndbi_t2_val,
                bsi=bsi_val,
                surface_px=region.get("size_pixels", 1),
                cloud_cover_pct=cloud_pct,
            )
            
            # TinyCD = mode expérimental. Poids entraînés sur images 0.5m (USA/Chine),
            # pas fiables sur Sentinel-2 10m (Afrique). Pas de bonus artificiel.
            region["confidence"] = conf
            return region

        # Régions nouvelles constructions
        construction_regions = calc.extract_change_regions(
            ndbi_results["changes"]["new_constructions"], min_region_size
        )
        for region in construction_regions:
            all_regions.append(enrich_region(region, "new_construction"))

        # Régions terrassement
        soil_regions = calc.extract_change_regions(
            ndbi_results["changes"]["soil_activity"], min_region_size
        )
        for region in soil_regions:
            all_regions.append(enrich_region(region, "soil_activity"))

        # Régions démolitions (L1 — NOUVEAU)
        if "demolished" in ndbi_results["changes"]:
            demolished_regions = calc.extract_change_regions(
                ndbi_results["changes"]["demolished"], min_region_size
            )
            for region in demolished_regions:
                all_regions.append(enrich_region(region, "demolition"))
            self.stdout.write(
                f"   → {len(demolished_regions)} démolitions potentielles détectées"
            )

        return all_regions

    # ─────────────────────────────────────────────────────────────────────
    def _pixel_region_to_geojson(self, region: dict, raster_transform) -> str:
        """
        Convertit une région raster (coordonnées pixels) en polygone GeoJSON WGS84.

        CORRECTIF A6 : l'ancienne implémentation utilisait les coordonnées pixels
        (lignes/colonnes) comme si c'étaient des longitudes/latitudes,
        ce qui produisait des géométries complètement hors de Treichville.

        On utilise maintenant le transform affine rasterio pour obtenir les vraies
        coordonnées géographiques (lon/lat en WGS84).

        Args:
            region:           Dict contenant 'centroid' (row, col) et 'size_pixels'
            raster_transform: Transform affine rasterio du raster source

        Returns:
            GeoJSON Polygon string avec coordonnées lon/lat.
        """
        centroid_row, centroid_col = region["centroid"]
        size_pixels = max(region.get("size_pixels", 10), 1)

        # Conversion centroid pixel → lon/lat
        lon_center, lat_center = rtransform.xy(
            raster_transform, centroid_row, centroid_col
        )

        # Estimation de la taille du polygone en degrés
        # sqrt(N pixels) × résolution pixel en degrés ÷ 2 → demi-côté
        half_side = (np.sqrt(size_pixels) * PIXEL_SIZE_DEGREES) / 2
        half_side = max(half_side, PIXEL_SIZE_DEGREES)  # minimum 1 pixel de côté

        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [lon_center - half_side, lat_center - half_side],
                [lon_center + half_side, lat_center - half_side],
                [lon_center + half_side, lat_center + half_side],
                [lon_center - half_side, lat_center + half_side],
                [lon_center - half_side, lat_center - half_side],  # fermeture
            ]],
        }
        return json.dumps(geometry)

    # ─────────────────────────────────────────────────────────────────────
    def process_4couches_verification(self, regions, image_t2):
        """Applique la vérification 4 couches et écrit les détections en BDD."""
        pipeline = DetectionPipeline()
        image_metadata = {
            "date_t2": str(image_t2.date_acquisition),
            "bands_t2": image_t2.bands,
        }
        with transaction.atomic():
            detections = pipeline.process_detection_regions(regions, image_metadata)

        image_t2.processed = True
        image_t2.save()
        return detections

    # ─────────────────────────────────────────────────────────────────────
    def print_detection_statistics(self):
        """Affiche les statistiques des détections dans la BDD."""
        self.stdout.write(self.style.SUCCESS("\n📊 STATISTIQUES FINALES"))

        total = DetectionConstruction.objects.count()
        if total == 0:
            self.stdout.write("   (Aucune détection en base)")
            return

        stats = (
            DetectionConstruction.objects.values("status")
            .annotate(count=models.Count("id"))
            .order_by("status")
        )
        self.stdout.write("   Par statut :")
        for s in stats:
            self.stdout.write(f"     {s['status']:<35} : {s['count']}")

        alert_stats = (
            DetectionConstruction.objects.values("alert_level")
            .annotate(count=models.Count("id"))
            .order_by("alert_level")
        )
        emoji_map = {"rouge": "🔴", "orange": "🟠", "vert": "🟢", "veille": "🔵"}
        self.stdout.write("   Par niveau d'alerte :")
        for a in alert_stats:
            emoji = emoji_map.get(a["alert_level"], "⚪")
            self.stdout.write(f"     {emoji} {a['alert_level']:<10} : {a['count']}")

        self.stdout.write(f"   TOTAL : {total} détections")
