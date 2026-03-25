"""
CIV-EYE — Commande de vérification et de lancement complet du pipeline.

VOLET 1 — VÉRIFICATION SYSTÈME
  Contrôle que toutes les conditions sont réunies pour lancer la détection :
  - Images Sentinel (ImageSatellite en base, fichiers TIF présents et lisibles)
  - Données bâtiments Google V3 (MicrosoftFootprint)
  - Zones cadastrales (ZoneCadastrale)
  - Poids TinyCD (model_weights.pth)
  - Connectivité GEE
  - Configuration Django

VOLET 2 — ANALYSE DE DÉTECTION
  Lance le pipeline complet (K-Means et/ou TinyCD) et enregistre les détections.
  Génère un rapport JSON structuré avec toutes les statistiques.

Usage :
  python manage.py pipeline_check                              (volets 1 + 2, mode K-Means)
  python manage.py pipeline_check --verify-only                (volet 1 uniquement)
  python manage.py pipeline_check --mode tinycd                (K-Means puis TinyCD)
  python manage.py pipeline_check --mode both                  (K-Means et TinyCD)
  python manage.py pipeline_check --clear-detections           (repart de zéro)
  python manage.py pipeline_check --date-t1 2024-02-15 --date-t2 2025-01-15
  python manage.py pipeline_check --output rapport_custom.json
"""

import json
import logging
import os
import sys
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

logger = logging.getLogger(__name__)

SEP = "=" * 68
SEP_LIGHT = "-" * 68
OK   = "✅"
WARN = "⚠️ "
FAIL = "❌"
INFO = "ℹ️ "


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_DATE_T1 = "2024-02-15"
DEFAULT_DATE_T2 = "2025-01-15"
WEIGHTS_PATH = os.path.join(
    "module1_urbanisme", "data_use", "weights", "model_weights.pth"
)
SENTINEL_DIR = os.path.join(
    "module1_urbanisme", "data_use", "sentinel_api_exports"
)
REQUIRED_BANDS = ["B04", "B08", "B11", "SCL"]
MIN_FOOTPRINTS = 1000
EXPECTED_CADASTRE = 19


class Command(BaseCommand):
    help = "Volet 1 : vérification système — Volet 2 : pipeline complet de détection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify-only", action="store_true",
            help="N'exécute que le volet 1 (vérification), sans lancer la détection",
        )
        parser.add_argument(
            "--mode", choices=["ai", "tinycd", "both"], default="ai",
            help="Mode de détection : ai=K-Means, tinycd=Deep Learning, both=les deux (défaut: ai)",
        )
        parser.add_argument(
            "--date-t1", type=str, default=DEFAULT_DATE_T1,
            help=f"Date image T1 (défaut: {DEFAULT_DATE_T1})",
        )
        parser.add_argument(
            "--date-t2", type=str, default=DEFAULT_DATE_T2,
            help=f"Date image T2 (défaut: {DEFAULT_DATE_T2})",
        )
        parser.add_argument(
            "--clear-detections", action="store_true",
            help="Supprimer toutes les détections existantes avant de relancer",
        )
        parser.add_argument(
            "--output", type=str, default="",
            help="Chemin du rapport JSON de sortie (auto-généré si absent)",
        )

    # ─────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        verify_only   = options["verify_only"]
        mode          = options["mode"]
        date_t1       = options["date_t1"]
        date_t2       = options["date_t2"]
        clear         = options["clear_detections"]
        output_path   = options["output"] or self._default_report_path()

        report = {
            "timestamp": datetime.now().isoformat(),
            "date_t1": date_t1,
            "date_t2": date_t2,
            "mode": "verify_only" if verify_only else mode,
            "volet1": {},
            "volet2": {},
        }

        # ══════════════════════════════════════════════════════════════════
        #  VOLET 1 — VÉRIFICATION SYSTÈME
        # ══════════════════════════════════════════════════════════════════
        self._header("VOLET 1 — VÉRIFICATION SYSTÈME")

        v1 = self._run_volet1(date_t1, date_t2)
        report["volet1"] = v1

        self._print_volet1_summary(v1)

        if verify_only:
            self._save_report(report, output_path)
            return

        # ══════════════════════════════════════════════════════════════════
        #  VOLET 2 — ANALYSE DE DÉTECTION
        # ══════════════════════════════════════════════════════════════════
        if not v1["go"]:
            self.stdout.write(self.style.ERROR(
                f"\n{FAIL} Volet 1 échoué — Volet 2 bloqué. Corrigez les erreurs ci-dessus.\n"
            ))
            report["volet2"]["skipped"] = True
            report["volet2"]["reason"] = "Volet 1 non validé"
            self._save_report(report, output_path)
            return

        self._header("VOLET 2 — ANALYSE DE DÉTECTION")

        if clear:
            self._clear_detections()

        v2 = self._run_volet2(mode, date_t1, date_t2, v1)
        report["volet2"] = v2

        self._print_volet2_summary(v2)
        self._save_report(report, output_path)

    # ─────────────────────────────────────────────────────────────────────
    # VOLET 1
    # ─────────────────────────────────────────────────────────────────────
    def _run_volet1(self, date_t1, date_t2):
        v1 = {
            "go": False,
            "checks": {},
            "errors": [],
            "warnings": [],
        }
        checks = v1["checks"]

        # 1. Django configuration
        self._step("1/8 — Configuration Django")
        try:
            from django.core.management import call_command
            from io import StringIO
            buf = StringIO()
            call_command("check", stdout=buf, stderr=buf)
            out = buf.getvalue()
            if "System check identified no issues" in out or out.strip() == "":
                self._ok("manage.py check : 0 problème")
                checks["django_check"] = True
            else:
                self._warn(f"manage.py check : {out.strip()[:120]}")
                checks["django_check"] = False
                v1["warnings"].append("Django check: " + out.strip()[:120])
        except Exception as e:
            self._fail(f"manage.py check impossible : {e}")
            checks["django_check"] = False
            v1["errors"].append(f"Django check: {e}")

        # 2. ImageSatellite — enregistrements en base
        self._step("2/8 — Images Sentinel en base (ImageSatellite)")
        try:
            from module1_urbanisme.models import ImageSatellite
            imgs = {str(img.date_acquisition): img for img in ImageSatellite.objects.all()}
            missing_dates = [d for d in [date_t1, date_t2] if d not in imgs]

            if missing_dates:
                self._fail(f"Dates manquantes en base : {missing_dates}")
                self._info("Lancer : python manage.py import_sentinel")
                checks["image_satellite"] = False
                v1["errors"].append(f"ImageSatellite manquantes : {missing_dates}")
            else:
                self._ok(f"T1={date_t1} et T2={date_t2} présents en base")
                checks["image_satellite"] = True
                checks["image_t1"] = imgs[date_t1]
                checks["image_t2"] = imgs[date_t2]
        except Exception as e:
            self._fail(f"Erreur accès ImageSatellite : {e}")
            checks["image_satellite"] = False
            v1["errors"].append(str(e))

        # 3. Fichiers TIF — présence sur disque et intégrité
        self._step("3/8 — Fichiers TIF Sentinel (lecture rasterio)")
        tif_ok = True
        tif_details = {}
        for date_str in [date_t1, date_t2]:
            tif_dir = os.path.join(str(settings.BASE_DIR), SENTINEL_DIR, date_str)
            date_ok = True
            bands_found = []
            bands_missing = []

            if not os.path.isdir(tif_dir):
                self._fail(f"Dossier absent : sentinel_api_exports/{date_str}/")
                tif_ok = False
                v1["errors"].append(f"Dossier TIF absent : {date_str}")
                continue

            for band in REQUIRED_BANDS:
                candidates = [
                    os.path.join(tif_dir, f"{band}_{date_str}.tif"),
                    os.path.join(tif_dir, f"{band}_{date_str}.tiff"),
                ]
                found = next((p for p in candidates if os.path.exists(p)), None)
                if found:
                    bands_found.append(band)
                    try:
                        import rasterio
                        with rasterio.open(found) as src:
                            _ = src.shape
                    except Exception as e:
                        self._fail(f"TIF corrompu {band}/{date_str} : {e}")
                        date_ok = False
                        v1["errors"].append(f"TIF corrompu {band}/{date_str}")
                else:
                    bands_missing.append(band)

            tif_details[date_str] = {"found": bands_found, "missing": bands_missing}

            scl_warn = "SCL" in bands_missing
            missing_critical = [b for b in bands_missing if b not in ("SCL", "B04")]
            if bands_missing:
                if missing_critical:
                    self._fail(f"{date_str} — Bandes critiques manquantes : {missing_critical}")
                    tif_ok = False
                    v1["errors"].append(f"Bandes manquantes {date_str}: {missing_critical}")
                elif scl_warn:
                    self._warn(f"{date_str} — SCL absent (masque nuages désactivé) — Bandes: {bands_found}")
                    v1["warnings"].append(f"SCL absent pour {date_str}")
            else:
                self._ok(f"{date_str} — Bandes: {', '.join(bands_found)} ✓")

            if not date_ok:
                tif_ok = False

        checks["tif_files"] = tif_ok
        checks["tif_details"] = tif_details

        # 4. Google Open Buildings V3 (MicrosoftFootprint)
        self._step("4/8 — Empreintes bâtiments Google V3")
        try:
            from module1_urbanisme.models import MicrosoftFootprint
            v3_count = MicrosoftFootprint.objects.filter(source="Google_V3_2023").count()
            total_fp = MicrosoftFootprint.objects.count()

            if v3_count == 0:
                self._fail(f"Aucun footprint Google_V3_2023 en base (total={total_fp})")
                self._info("Lancer : python manage.py import_google_buildings")
                checks["footprints"] = False
                v1["errors"].append("Aucun footprint Google V3 en base")
            elif v3_count < MIN_FOOTPRINTS:
                self._warn(f"Seulement {v3_count:,} footprints V3 (minimum conseillé : {MIN_FOOTPRINTS:,})")
                checks["footprints"] = True
                v1["warnings"].append(f"Peu de footprints V3 : {v3_count:,}")
            else:
                self._ok(f"Google_V3_2023 : {v3_count:,} empreintes (total en base : {total_fp:,})")
                checks["footprints"] = True
            checks["footprint_count"] = {"v3": v3_count, "total": total_fp}
        except Exception as e:
            self._fail(f"Erreur accès MicrosoftFootprint : {e}")
            checks["footprints"] = False
            v1["errors"].append(str(e))

        # 5. Zones cadastrales
        self._step("5/8 — Zones cadastrales (ZoneCadastrale)")
        try:
            from module1_urbanisme.models import ZoneCadastrale
            cad_count = ZoneCadastrale.objects.count()
            if cad_count == 0:
                self._fail("Aucune zone cadastrale en base")
                self._info("Lancer : python manage.py import_cadastre")
                checks["cadastre"] = False
                v1["errors"].append("Aucune zone cadastrale")
            elif cad_count < EXPECTED_CADASTRE:
                self._warn(f"Seulement {cad_count}/{EXPECTED_CADASTRE} zones cadastrales")
                checks["cadastre"] = True
                v1["warnings"].append(f"Zones cadastrales partielles : {cad_count}/{EXPECTED_CADASTRE}")
            else:
                from django.db.models import Count
                by_status = dict(ZoneCadastrale.objects.values_list("buildable_status").annotate(c=Count("id")))
                self._ok(
                    f"{cad_count} zones — "
                    f"Constructible: {by_status.get('buildable', 0)} | "
                    f"Conditionnel: {by_status.get('conditional', 0)} | "
                    f"Interdit: {by_status.get('forbidden', 0)}"
                )
                checks["cadastre"] = True
            checks["cadastre_count"] = cad_count
        except Exception as e:
            self._fail(f"Erreur accès ZoneCadastrale : {e}")
            checks["cadastre"] = False
            v1["errors"].append(str(e))

        # 6. Poids TinyCD
        self._step("6/8 — Poids TinyCD (model_weights.pth)")
        weights_abs = os.path.join(str(settings.BASE_DIR), WEIGHTS_PATH)
        if os.path.exists(weights_abs):
            size_mb = os.path.getsize(weights_abs) / 1_048_576
            self._ok(f"model_weights.pth présent ({size_mb:.1f} Mo)")
            checks["tinycd_weights"] = True
        else:
            self._warn(
                "model_weights.pth absent — TinyCD désactivé\n"
                "         Télécharger : https://github.com/AndreaCodegoni/Tiny_model_4_CD → pretrained_models/levir_best.pth\n"
                "         → Renommer en model_weights.pth dans module1_urbanisme/data_use/weights/"
            )
            checks["tinycd_weights"] = False
            v1["warnings"].append("model_weights.pth absent — TinyCD indisponible")

        # 7. Connectivité GEE
        self._step("7/8 — Google Earth Engine")
        try:
            import ee
            project_id = os.getenv("GEE_PROJECT_ID", "").strip()
            if project_id:
                ee.Initialize(project=project_id)
                self._ok(f"GEE connecté — projet : {project_id}")
                checks["gee"] = True
            else:
                self._warn("GEE_PROJECT_ID absent dans .env — GEE désactivé")
                checks["gee"] = False
                v1["warnings"].append("GEE_PROJECT_ID absent")
        except ImportError:
            self._warn("earthengine-api non installé (pip install earthengine-api)")
            checks["gee"] = False
        except Exception as e:
            self._warn(f"GEE non initialisé : {type(e).__name__} — lancer ee.Authenticate()")
            checks["gee"] = False
            v1["warnings"].append(f"GEE: {e}")

        # 8. Détections existantes
        self._step("8/8 — Détections existantes")
        try:
            from module1_urbanisme.models import DetectionConstruction
            from django.db.models import Count
            total_det = DetectionConstruction.objects.count()
            by_status = list(
                DetectionConstruction.objects.values("status", "alert_level")
                .annotate(count=Count("id"))
                .order_by("alert_level")
            )
            checks["detections_existing"] = total_det
            checks["detections_by_status"] = by_status
            if total_det == 0:
                self._info("Aucune détection en base (sera créé au volet 2)")
            else:
                emoji_map = {"rouge": "🔴", "orange": "🟠", "veille": "🔵", "vert": "🟢"}
                summary = " | ".join(
                    f"{emoji_map.get(s['alert_level'], '⚪')} {s['status']}: {s['count']}"
                    for s in by_status
                )
                self._ok(f"{total_det} détections en base — {summary}")
        except Exception as e:
            self._warn(f"Erreur lecture détections : {e}")
            checks["detections_existing"] = 0

        # ── GO/NO-GO ──────────────────────────────────────────────────────
        critical = ["django_check", "image_satellite", "tif_files", "footprints", "cadastre"]
        all_critical_ok = all(checks.get(c, False) for c in critical)
        v1["go"] = all_critical_ok
        return v1

    # ─────────────────────────────────────────────────────────────────────
    # VOLET 2
    # ─────────────────────────────────────────────────────────────────────
    def _run_volet2(self, mode, date_t1, date_t2, v1):
        from django.core.management import call_command
        from io import StringIO

        v2 = {
            "mode": mode,
            "date_t1": date_t1,
            "date_t2": date_t2,
            "runs": [],
            "final_stats": {},
        }

        # Définir les modes à lancer
        modes_to_run = []
        if mode in ("ai", "both"):
            modes_to_run.append(("ai", "--use-ai"))
        if mode in ("tinycd", "both"):
            if v1["checks"].get("tinycd_weights"):
                modes_to_run.append(("tinycd", "--use-tinycd"))
            else:
                self._warn("TinyCD ignoré — model_weights.pth absent")
                v2["tinycd_skipped"] = True

        for mode_name, mode_flag in modes_to_run:
            self._step(f"Détection {mode_name.upper()} (T1={date_t1} → T2={date_t2})")
            buf = StringIO()
            run_result = {"mode": mode_name, "success": False, "error": None, "detections_created": 0}

            try:
                kwargs = {
                    "date_t1": date_t1,
                    "date_t2": date_t2,
                    "stdout": buf,
                    "stderr": buf,
                }
                if mode_flag == "--use-ai":
                    kwargs["use_ai"] = True
                elif mode_flag == "--use-tinycd":
                    kwargs["use_tinycd"] = True

                call_command("run_detection", **kwargs)

                output = buf.getvalue()
                # Extraire le nombre de détections créées
                for line in output.split("\n"):
                    if "détections créées en base" in line:
                        try:
                            run_result["detections_created"] = int(
                                line.strip().split("→")[1].strip().split()[0]
                            )
                        except Exception:
                            pass

                run_result["success"] = True
                self._ok(f"{mode_name.upper()} terminé — {run_result['detections_created']} détections créées")

            except CommandError as e:
                run_result["error"] = str(e)
                self._fail(f"{mode_name.upper()} erreur CommandError : {e}")
            except Exception as e:
                run_result["error"] = str(e)
                self._fail(f"{mode_name.upper()} erreur : {e}")

            v2["runs"].append(run_result)

        # Statistiques finales après tous les runs
        v2["final_stats"] = self._get_detection_stats()
        return v2

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────
    def _clear_detections(self):
        from module1_urbanisme.models import DetectionConstruction
        deleted = DetectionConstruction.objects.all().delete()[0]
        self._warn(f"--clear-detections : {deleted} détections supprimées")

    def _get_detection_stats(self):
        try:
            from module1_urbanisme.models import DetectionConstruction
            from django.db.models import Count
            total = DetectionConstruction.objects.count()
            by_status = {
                s["status"]: s["count"]
                for s in DetectionConstruction.objects.values("status").annotate(count=Count("id"))
            }
            by_alert = {
                s["alert_level"]: s["count"]
                for s in DetectionConstruction.objects.values("alert_level").annotate(count=Count("id"))
            }
            return {"total": total, "by_status": by_status, "by_alert": by_alert}
        except Exception as e:
            return {"error": str(e)}

    def _print_volet1_summary(self, v1):
        self.stdout.write(f"\n{SEP_LIGHT}")
        self.stdout.write("  RÉSUMÉ VOLET 1")
        self.stdout.write(SEP_LIGHT)
        errors = v1.get("errors", [])
        warnings = v1.get("warnings", [])
        if errors:
            for e in errors:
                self.stdout.write(self.style.ERROR(f"  {FAIL} {e}"))
        if warnings:
            for w in warnings:
                self.stdout.write(self.style.WARNING(f"  {WARN} {w}"))
        if v1["go"]:
            self.stdout.write(self.style.SUCCESS(f"\n  {OK} SYSTÈME OPÉRATIONNEL — Pipeline prêt au lancement\n"))
        else:
            self.stdout.write(self.style.ERROR(f"\n  {FAIL} SYSTÈME NON OPÉRATIONNEL — {len(errors)} erreur(s) bloquante(s)\n"))

    def _print_volet2_summary(self, v2):
        self.stdout.write(f"\n{SEP_LIGHT}")
        self.stdout.write("  RÉSUMÉ VOLET 2")
        self.stdout.write(SEP_LIGHT)
        stats = v2.get("final_stats", {})
        total = stats.get("total", 0)
        by_alert = stats.get("by_alert", {})
        emoji_map = {"rouge": "🔴", "orange": "🟠", "veille": "🔵", "vert": "🟢"}
        self.stdout.write(self.style.SUCCESS(f"\n  {OK} DÉTECTION COMPLÈTE — {total} détections en base"))
        for level, count in by_alert.items():
            self.stdout.write(f"     {emoji_map.get(level, '⚪')} {level:<10} : {count}")

    def _save_report(self, report, output_path):
        try:
            # Nettoyer les objets Django non-sérialisables avant la sauvegarde
            v1 = report.get("volet1", {})
            checks = v1.get("checks", {})
            for key in ("image_t1", "image_t2"):
                if key in checks:
                    img = checks[key]
                    checks[key] = {
                        "id": img.pk,
                        "date": str(img.date_acquisition),
                        "bands": img.bands,
                        "scl": str(img.classification_map) if img.classification_map else None,
                    }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)

            self.stdout.write(self.style.SUCCESS(f"\n📄 Rapport sauvegardé : {output_path}\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n{FAIL} Erreur sauvegarde rapport : {e}"))

    def _default_report_path(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"pipeline_report_{ts}.json"

    # ── Affichage ──────────────────────────────────────────────────────────
    def _header(self, title):
        self.stdout.write(f"\n{SEP}")
        self.stdout.write(f"  {title}")
        self.stdout.write(f"{SEP}\n")

    def _step(self, label):
        self.stdout.write(f"\n  {INFO} {label}")

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"     {OK} {msg}"))

    def _warn(self, msg):
        self.stdout.write(self.style.WARNING(f"     {WARN} {msg}"))

    def _fail(self, msg):
        self.stdout.write(self.style.ERROR(f"     {FAIL} {msg}"))

    def _info(self, msg):
        self.stdout.write(f"         → {msg}")
