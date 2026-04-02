#!/usr/bin/env python3
"""
CIV-EYE — Lanceur du pipeline complet de détection
=====================================================

Exécute l'intégralité du pipeline : vérification, détection, puis affiche
TOUTES les détections de manière lisible dans le terminal.

Usage :
  python run_pipeline.py                          (K-Means, T1=2024-02-15 T2=2025-01-15)
  python run_pipeline.py --mode tinycd            (TinyCD Deep Learning)
  python run_pipeline.py --mode both              (K-Means + TinyCD)
  python run_pipeline.py --clear                  (efface les détections existantes)
  python run_pipeline.py --show-only              (affiche seulement les détections en base)
  python run_pipeline.py --date-t1 2024-02-15 --date-t2 2025-01-15
  python run_pipeline.py --filter rouge           (affiche seulement les alertes rouges)
  python run_pipeline.py --export detections.json (exporte en GeoJSON)

Niveaux d'alerte :
  [ROUGE]  infraction_zonage    Construction illégale avérée
  [ORANGE] sous_condition       Construction en zone conditionnelle
  [VEILLE] surveillance_preventive  Changement à surveiller
  [VERT]   conforme             Construction conforme au zonage
"""

import os
import sys
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION DJANGO
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django
    django.setup()
except Exception as e:
    print(f"\n  [FAIL] Impossible de démarrer Django : {e}")
    print("         Vérifier que DJANGO_SETTINGS_MODULE est correct et que les dépendances sont installées.")
    sys.exit(1)

# Import après setup Django
from django.core.management import call_command
from django.db import models
from io import StringIO

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_DATE_T1 = "2024-02-15"
DEFAULT_DATE_T2 = "2025-01-15"

SEP     = "=" * 72
SEP_LGT = "-" * 72
SEP_MID = "·" * 72

ALERT_EMOJI = {
    "rouge":   "🔴 [ROUGE] ",
    "orange":  "🟠 [ORANGE]",
    "veille":  "🔵 [VEILLE]",
    "vert":    "🟢 [VERT]  ",
}

STATUS_LABEL = {
    "infraction_zonage":       "INFRACTION ZONAGE",
    "sous_condition":          "SOUS CONDITION",
    "surveillance_preventive": "SURVEILLANCE",
    "conforme":                "CONFORME",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS D'AFFICHAGE
# ─────────────────────────────────────────────────────────────────────────────

def banner():
    print()
    print(SEP)
    print("  CIV-EYE MODULE 1 — PIPELINE COMPLET DE DÉTECTION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)


def section(title, icon=""):
    print()
    print(SEP)
    print(f"  {icon}  {title}" if icon else f"  {title}")
    print(SEP)
    print()


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


def info(msg):
    print(f"  [INFO] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — VÉRIFICATION SYSTÈME (résumé rapide)
# ─────────────────────────────────────────────────────────────────────────────

def verify_prerequisites(date_t1, date_t2):
    """Vérifie les prérequis critiques. Retourne True si OK pour continuer."""
    section("VÉRIFICATION SYSTÈME", "🔍")

    from module1_urbanisme.models import ImageSatellite, ZoneCadastrale, MicrosoftFootprint

    all_ok = True

    # Images Sentinel — AUTO-ACQUISITION SI MANQUANT
    imgs_in_db = {str(img.date_acquisition): img for img in ImageSatellite.objects.all()}
    missing_dates = [d for d in [date_t1, date_t2] if d not in imgs_in_db]

    if missing_dates:
        info(f"Données Sentinel manquantes pour : {missing_dates}")
        info("  🔄 Tentative d'auto-acquisition via API (CDSE Copernicus Gratuit)...")
        for d in missing_dates:
            try:
                # Appelle la commande d'import API automatiquement
                call_command('import_sentinel_api', date=d)
                ok(f"Acquisition réussie pour {d}")
            except Exception as e:
                fail(f"Échec de l'auto-acquisition pour {d} : {e}")
                all_ok = False
        
        # Rafraîchir la liste après acquisition
        imgs_in_db = {str(img.date_acquisition): img for img in ImageSatellite.objects.all()}

    for d in [date_t1, date_t2]:
        if d in imgs_in_db:
            img = imgs_in_db[d]
            b = list(img.bands.keys()) if img.bands else []
            scl = "SCL OK" if (img.classification_map and os.path.exists(str(img.classification_map))) else "SCL absent"
            ok(f"ImageSatellite {d} — Bandes : {b} | {scl}")

    # Vérification des fichiers TIF sur disque (et retéléchargement si besoin)
    for d, img in [(d, imgs_in_db[d]) for d in [date_t1, date_t2] if d in imgs_in_db]:
        paths_exist = [os.path.exists(str(p)) for p in (img.bands or {}).values()]
        if not all(paths_exist):
            warn(f"Certains fichiers TIF manquent pour {d} sur le disque. Tentative de restauration...")
            try:
                call_command('import_sentinel_api', date=d)
                ok(f"Fichiers restaurés pour {d}")
            except Exception as e:
                fail(f"Impossible de restaurer les fichiers pour {d} : {e}")
                all_ok = False

    # Google V3 footprints
    v3_count = MicrosoftFootprint.objects.filter(source="Google_V3_2023").count()
    if v3_count == 0:
        fail("Aucun footprint Google_V3_2023 en base")
        fail("  → Lancer : python manage.py import_google_buildings")
        all_ok = False
    else:
        ok(f"Footprints Google V3 : {v3_count:,} empreintes")

    # Zones cadastrales
    cad = ZoneCadastrale.objects.count()
    if cad == 0:
        fail("Aucune zone cadastrale")
        fail("  → Lancer : python manage.py import_cadastre")
        all_ok = False
    else:
        ok(f"Zones cadastrales : {cad}")

    if all_ok:
        print()
        ok("PRÉREQUIS VALIDÉS — Pipeline prêt au lancement")
    else:
        print()
        fail("PRÉREQUIS MANQUANTS — Corriger les erreurs ci-dessus avant de continuer")

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — EXÉCUTION DU PIPELINE (K-Means et/ou TinyCD)
# ─────────────────────────────────────────────────────────────────────────────

def run_detection(mode, date_t1, date_t2, clear):
    """Lance le pipeline de détection via call_command. Retourne le nb de détections créées."""
    from module1_urbanisme.models import DetectionConstruction

    if clear:
        deleted = DetectionConstruction.objects.all().delete()[0]
        warn(f"Suppression des détections existantes : {deleted} supprimée(s)")

    modes_to_run = []
    if mode in ("kmeans", "ai", "both"):
        modes_to_run.append(("K-Means AI", {"use_ai": True}))
    if mode in ("tinycd", "both"):
        modes_to_run.append(("TinyCD Deep Learning", {"use_tinycd": True}))

    total_created = 0

    for label, kwargs in modes_to_run:
        section(f"DÉTECTION — {label}", "🤖")
        print(f"  T1 = {date_t1}  →  T2 = {date_t2}")
        print()

        t0 = time.time()

        # On laisse call_command afficher directement dans le terminal
        try:
            call_command(
                "run_detection",
                date_t1=date_t1,
                date_t2=date_t2,
                **kwargs,
            )
        except Exception as e:
            fail(f"Erreur pipeline {label} : {e}")
            import traceback
            traceback.print_exc()
            continue

        elapsed = time.time() - t0
        new_count = DetectionConstruction.objects.count()
        info(f"Durée {label} : {elapsed:.1f}s — Total détections en base : {new_count:,}")
        total_created = new_count

    return total_created


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — AFFICHAGE DE TOUTES LES DÉTECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def display_all_detections(alert_filter=None):
    """Affiche toutes les détections en base de manière lisible."""
    from module1_urbanisme.models import DetectionConstruction
    from django.db.models import Count, Avg

    section("TOUTES LES DÉTECTIONS EN BASE", "📋")

    qs = DetectionConstruction.objects.select_related("zone_cadastrale").order_by(
        "alert_level", "-confidence", "-date_detection"
    )

    if alert_filter:
        qs = qs.filter(alert_level=alert_filter)
        info(f"Filtre actif : alert_level = {alert_filter}")

    total = qs.count()

    if total == 0:
        warn("Aucune détection en base.")
        if not alert_filter:
            warn("  → Lancer : python run_pipeline.py  (sans --show-only)")
        return

    info(f"{total} détection(s) à afficher")
    print()

    # ── Tableau par niveau d'alerte ──────────────────────────────────────────
    current_level = None

    for d in qs:
        level = d.alert_level
        if level != current_level:
            current_level = level
            emoji = ALERT_EMOJI.get(level, "⚪ [?????] ")
            print()
            print(SEP_LGT)
            print(f"  {emoji}  {STATUS_LABEL.get(d.status, d.status.upper())}")
            print(SEP_LGT)
            print(f"  {'ID':>6}  {'Date':>12}  {'Zone':<28}  {'Conf':>5}  {'NDBI-T1':>8}  {'NDBI-T2':>8}  {'Surf(m²)':>9}  {'Lat':>10}  {'Lon':>10}")
            print(SEP_MID)

        # Coordonnées
        lat_str = f"{d.latitude:.5f}" if d.latitude is not None else "    N/A  "
        lon_str = f"{d.longitude:.5f}" if d.longitude is not None else "    N/A  "

        # Zone
        zone_name = (d.zone_cadastrale.name if d.zone_cadastrale else "—")[:28]

        # Surface
        surf = f"{d.surface_m2:.0f}" if d.surface_m2 else "—"

        # Date
        date_str = str(d.date_detection)[:10] if d.date_detection else "—"

        print(
            f"  {d.id:>6}  {date_str:>12}  {zone_name:<28}  "
            f"{d.confidence:>5.2f}  {d.ndbi_t1:>8.4f}  {d.ndbi_t2:>8.4f}  "
            f"{surf:>9}  {lat_str:>10}  {lon_str:>10}"
        )

    print()
    print(SEP_LGT)


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 4 — STATISTIQUES GLOBALES
# ─────────────────────────────────────────────────────────────────────────────

def display_statistics():
    """Affiche les statistiques complètes des détections."""
    from module1_urbanisme.models import DetectionConstruction
    from django.db.models import Count, Avg, Min, Max

    section("STATISTIQUES COMPLÈTES", "📊")

    total = DetectionConstruction.objects.count()
    if total == 0:
        warn("Aucune statistique disponible (base vide)")
        return

    # ── Par niveau d'alerte ──
    print("  PAR NIVEAU D'ALERTE :")
    print(f"  {'Niveau':<12}  {'Nb':>6}  {'%':>6}  {'Conf moy':>10}  {'Surf moy(m²)':>14}")
    print(SEP_MID)

    by_alert = (
        DetectionConstruction.objects
        .values("alert_level")
        .annotate(
            count=Count("id"),
            avg_conf=Avg("confidence"),
            avg_surf=Avg("surface_m2"),
        )
        .order_by("alert_level")
    )

    for row in by_alert:
        emoji = ALERT_EMOJI.get(row["alert_level"], "⚪ ?")
        pct = row["count"] / total * 100
        avg_c = f"{row['avg_conf']:.2f}" if row["avg_conf"] is not None else "—"
        avg_s = f"{row['avg_surf']:.0f}" if row["avg_surf"] is not None else "—"
        print(f"  {emoji}  {row['count']:>6}  {pct:>5.1f}%  {avg_c:>10}  {avg_s:>14}")

    print(SEP_MID)
    print(f"  {'TOTAL':<14}  {total:>6}")

    # ── Par zone cadastrale ──
    print()
    print("  PAR ZONE CADASTRALE (top 15) :")
    print(f"  {'Zone':<32}  {'Nb':>6}  {'Conf moy':>10}  {'Alerte dominante':<16}")
    print(SEP_MID)

    from django.db.models import F
    by_zone = (
        DetectionConstruction.objects
        .values("zone_cadastrale__name")
        .annotate(count=Count("id"), avg_conf=Avg("confidence"))
        .order_by("-count")[:15]
    )

    for row in by_zone:
        zone = (row["zone_cadastrale__name"] or "—")[:32]
        avg_c = f"{row['avg_conf']:.2f}" if row["avg_conf"] is not None else "—"
        # Alerte dominante pour cette zone
        dom = (
            DetectionConstruction.objects
            .filter(zone_cadastrale__name=row["zone_cadastrale__name"])
            .values("alert_level")
            .annotate(c=Count("id"))
            .order_by("-c")
            .first()
        )
        dom_label = ALERT_EMOJI.get(dom["alert_level"], "?") if dom else "?"
        print(f"  {zone:<32}  {row['count']:>6}  {avg_c:>10}  {dom_label}")

    # ── Intervalle NDBI ──
    print()
    print("  INTERVALLE NDBI :")
    stats = DetectionConstruction.objects.aggregate(
        min_t1=Min("ndbi_t1"), max_t1=Max("ndbi_t1"),
        min_t2=Min("ndbi_t2"), max_t2=Max("ndbi_t2"),
        avg_conf=Avg("confidence"),
    )
    print(f"  NDBI T1 : min={stats['min_t1']:.4f}  max={stats['max_t1']:.4f}")
    print(f"  NDBI T2 : min={stats['min_t2']:.4f}  max={stats['max_t2']:.4f}")
    print(f"  Confiance moyenne globale : {stats['avg_conf']:.3f}" if stats["avg_conf"] else "  Confiance : —")

    print()
    ok(f"Analyse complète de {total} détection(s) affichée.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT GEOJSON
# ─────────────────────────────────────────────────────────────────────────────

def export_geojson(output_path):
    """Exporte toutes les détections en GeoJSON."""
    from module1_urbanisme.models import DetectionConstruction

    detections = DetectionConstruction.objects.all().order_by("alert_level", "-confidence")
    features = []

    for d in detections:
        geom = None
        if d.geometry:
            try:
                geom = json.loads(d.geometry.json)
            except Exception:
                pass

        feat = {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "id": d.id,
                "status": d.status,
                "alert_level": d.alert_level,
                "confidence": round(d.confidence, 4),
                "ndbi_t1": round(d.ndbi_t1, 4),
                "ndbi_t2": round(d.ndbi_t2, 4),
                "bsi_value": round(d.bsi_value, 4) if d.bsi_value is not None else None,
                "surface_m2": round(d.surface_m2, 1) if d.surface_m2 else None,
                "zone_name": d.zone_name,
                "zone_type": d.zone_type,
                "date_detection": str(d.date_detection)[:10] if d.date_detection else None,
                "latitude": d.latitude,
                "longitude": d.longitude,
            },
        }
        features.append(feat)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    ok(f"Exporté {len(features)} détections → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    args = sys.argv[1:]
    opts = {
        "mode": "kmeans",
        "date_t1": DEFAULT_DATE_T1,
        "date_t2": DEFAULT_DATE_T2,
        "clear": False,
        "show_only": False,
        "filter": None,
        "export": None,
    }

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--mode" and i + 1 < len(args):
            # On accepte 'kmeans', 'ai' ou 'tinycd'
            mode_val = args[i + 1].lower()
            if mode_val == "ai": mode_val = "kmeans"
            opts["mode"] = mode_val; i += 2
        elif a == "--date-t1" and i + 1 < len(args):
            opts["date_t1"] = args[i + 1]; i += 2
        elif a == "--date-t2" and i + 1 < len(args):
            opts["date_t2"] = args[i + 1]; i += 2
        elif a == "--clear":
            opts["clear"] = True; i += 1
        elif a == "--show-only":
            opts["show_only"] = True; i += 1
        elif a == "--filter" and i + 1 < len(args):
            opts["filter"] = args[i + 1]; i += 2
        elif a == "--export" and i + 1 < len(args):
            opts["export"] = args[i + 1]; i += 2
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"  [WARN] Argument inconnu ignoré : {a}")
            i += 1

    return opts


def main():
    opts = parse_args()

    banner()
    print(f"  Mode           : {opts['mode'].upper()}")
    print(f"  T1             : {opts['date_t1']}")
    print(f"  T2             : {opts['date_t2']}")
    print(f"  Clear existing : {'Oui' if opts['clear'] else 'Non'}")
    print(f"  Affichage seul : {'Oui' if opts['show_only'] else 'Non'}")
    if opts["filter"]:
        print(f"  Filtre alerte  : {opts['filter']}")
    if opts["export"]:
        print(f"  Export GeoJSON : {opts['export']}")

    t_total = time.time()

    # ─── Mode affichage seul ────────────────────────────────────────────────
    if opts["show_only"]:
        display_all_detections(alert_filter=opts["filter"])
        display_statistics()
        if opts["export"]:
            export_geojson(opts["export"])
        print(f"  Durée totale : {time.time() - t_total:.1f}s")
        return

    # ─── Pipeline complet ───────────────────────────────────────────────────

    # 1. Vérification
    if not verify_prerequisites(opts["date_t1"], opts["date_t2"]):
        print()
        fail("Pipeline annulé — Corriger les prérequis.")
        sys.exit(1)

    # 2. Détection
    run_detection(
        mode=opts["mode"],
        date_t1=opts["date_t1"],
        date_t2=opts["date_t2"],
        clear=opts["clear"],
    )

    # 3. Affichage des détections
    display_all_detections(alert_filter=opts["filter"])

    # 4. Statistiques
    display_statistics()

    # 5. Export optionnel
    if opts["export"]:
        export_geojson(opts["export"])

    # ─── Résumé final ───────────────────────────────────────────────────────
    elapsed = time.time() - t_total
    print()
    print(SEP)
    print(f"  Pipeline terminé en {elapsed:.1f}s  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)
    print()


if __name__ == "__main__":
    main()
