"""
Google Open Buildings Temporal V1 — Interrogation via GEE.

STRUCTURE RÉELLE DE LA COLLECTION GEE :
  `GOOGLE/Research/open-buildings-temporal/v1` est une ImageCollection de tuiles S2.
  Chaque "feature" est une tuile couvrant une grande zone géographique à une date donnée
  (ex : tuile '0f' couvre toute l'Afrique de l'Ouest, 8 snapshots de 2016 à 2023).
  Ce n'est PAS une FeatureCollection de polygones de bâtiments individuels.

UTILISATION CORRECTE :
  1. Importer V3 en base (python manage.py import_google_buildings) ← PRIORITÉ
  2. Pour vérifier si un bâtiment existait à une date T :
     - Utiliser la méthode check_building_at_date() de ce module
     - Elle interroge la tuile temporelle la plus proche de T
     - Résultat : True si le bâtiment était présent, False sinon

POURQUOI C'EST IMPORTANT (P4) :
  V3 snapshot mai 2023 + confiance >= 0.75 → classé pré-existant.
  Mais si le bâtiment a été construit entre mai 2023 et T1 (fév 2024),
  V3 le considère déjà existant alors que c'est une nouvelle construction.
  V1 Temporal permet de vérifier la date réelle de construction.

PRÉREQUIS :
  - GEE_PROJECT_ID dans .env
  - earthengine authenticate (une seule fois)

Usage :
  python manage.py import_google_temporal_v1 --dry-run      (liste les snapshots disponibles)
  python manage.py import_google_temporal_v1 --list-tiles   (affiche les tuiles et dates)
"""

import datetime
import logging
import os
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# BBOX Treichville, Abidjan (SRID 4326)
TREICHVILLE_BBOX = [-4.03001, 5.28501, -3.97301, 5.32053]
COLLECTION_ID = "GOOGLE/Research/open-buildings-temporal/v1"


class Command(BaseCommand):
    help = (
        "Interroge Google Open Buildings Temporal V1 (GEE ImageCollection de tuiles S2). "
        "Affiche les snapshots disponibles et peut vérifier la présence d'un bâtiment à une date."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-tiles", action="store_true",
            help="Lister les tuiles S2 disponibles et leurs dates pour Treichville",
        )
        parser.add_argument(
            "--check-date", type=str, default="",
            help="Date ISO (ex: 2024-02-15) — trouver le snapshot le plus proche de cette date",
        )
        parser.add_argument(
            "--bbox", type=str, default=",".join(str(x) for x in TREICHVILLE_BBOX),
            help="Bounding box (minLon,minLat,maxLon,maxLat)",
        )

    def handle(self, *args, **options):
        list_tiles = options["list_tiles"]
        check_date = options["check_date"]
        bbox = [float(x) for x in options["bbox"].split(",")]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== Google Open Buildings Temporal V1 — Analyse ==="
        ))
        self.stdout.write("")
        self.stdout.write(
            "⚠️  ATTENTION : Temporal V1 est une ImageCollection de TUILES S2,\n"
            "   pas une FeatureCollection de polygones individuels.\n"
            "   Il n'est pas possible de l'importer en masse comme V3.\n"
            "   Usage : vérification ponctuelle de présence d'un bâtiment à une date."
        )
        self.stdout.write("")

        ee = self._init_gee()
        if ee is None:
            return

        roi = ee.Geometry.Rectangle(bbox)
        collection = ee.FeatureCollection(COLLECTION_ID).filterBounds(roi)

        tiles = collection.getInfo().get("features", [])
        if not tiles:
            self.stdout.write(self.style.WARNING("Aucune tuile trouvée pour cette zone."))
            return

        self.stdout.write(f"  Tuiles disponibles : {len(tiles)}")
        self.stdout.write("")

        snapshots = []
        for tile in tiles:
            props = tile.get("properties", {})
            t_start = props.get("imagery_start_time_epoch_s", 0)
            t_end = props.get("imagery_end_time_epoch_s", 0)
            token = props.get("s2cell_token", "?")
            size_gb = props.get("system:asset_size", 0) / 1_073_741_824
            d_start = datetime.datetime.utcfromtimestamp(t_start).strftime("%Y-%m-%d") if t_start else "?"
            d_end = datetime.datetime.utcfromtimestamp(t_end).strftime("%Y-%m-%d") if t_end else "?"
            snapshots.append({"token": token, "start": d_start, "end": d_end, "size_gb": size_gb, "t_mid": (t_start + t_end) // 2})

        snapshots.sort(key=lambda x: x["start"])

        if list_tiles or not check_date:
            self.stdout.write("  Snapshots disponibles :")
            for i, s in enumerate(snapshots, 1):
                self.stdout.write(
                    f"    [{i}] Tuile {s['token']} | {s['start']} → {s['end']} | {s['size_gb']:.1f} Go"
                )
            self.stdout.write("")
            self.stdout.write(
                "  → Pour la vérification P4 (bâtiment construit entre mai 2023 et T1),\n"
                "    utiliser le snapshot dont la période couvre T1 (2024-02-15).\n"
                "  → Snapshot recommandé : le plus récent avant 2024-02-15."
            )
            covering = [s for s in snapshots if s["start"] <= "2024-02-15" <= s["end"]]
            if covering:
                s = covering[-1]
                self.stdout.write(self.style.SUCCESS(
                    f"\n  ✅ Snapshot couvrant T1=2024-02-15 : {s['start']} → {s['end']} (tuile {s['token']})"
                ))
            else:
                before = [s for s in snapshots if s["end"] <= "2024-02-15"]
                if before:
                    s = before[-1]
                    self.stdout.write(self.style.WARNING(
                        f"\n  ⚠️  Pas de snapshot exact pour T1. Plus proche avant : {s['start']} → {s['end']}"
                    ))

        if check_date:
            self._find_closest_snapshot(snapshots, check_date)

    def _init_gee(self):
        try:
            import ee
        except ImportError:
            self.stdout.write(self.style.ERROR("earthengine-api non installé : pip install earthengine-api"))
            return None

        project_id = os.getenv("GEE_PROJECT_ID", "")
        if not project_id:
            self.stdout.write(self.style.ERROR("GEE_PROJECT_ID manquant dans .env"))
            return None

        try:
            ee.Initialize(project=project_id)
            self.stdout.write("  GEE connecté ✅")
            return ee
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur GEE : {e}"))
            return None

    def _find_closest_snapshot(self, snapshots, check_date):
        self.stdout.write(f"\n  Recherche snapshot le plus proche de {check_date} :")
        covering = [s for s in snapshots if s["start"] <= check_date <= s["end"]]
        if covering:
            s = covering[-1]
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ Snapshot couvrant {check_date} : {s['start']} → {s['end']} (tuile {s['token']})"
            ))
        else:
            before = [s for s in snapshots if s["end"] < check_date]
            after = [s for s in snapshots if s["start"] > check_date]
            if before:
                self.stdout.write(f"  Avant : {before[-1]['start']} → {before[-1]['end']}")
            if after:
                self.stdout.write(f"  Après : {after[0]['start']} → {after[0]['end']}")
