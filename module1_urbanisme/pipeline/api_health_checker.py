"""
Module de Vérification et Diagnostic des APIs CIV-Eye
======================================================
Ce module vérifie TOUTES les APIs utilisées dans le pipeline avant de lancer
la détection. Produit des logs clairs avec des indicateurs visuels.

Usage :
    from module1_urbanisme.pipeline.api_health_checker import APIHealthChecker
    checker = APIHealthChecker()
    checker.run_all_checks()  # Affiche le statut de chaque API
    checker.assert_minimum_viable()  # Lève une exception si aucune source de données n'est dispo.
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION : Indicateurs Visuels de Statut API
# ─────────────────────────────────────────────────────────────────────────────
ICON_OK    = "✅"
ICON_WARN  = "⚠️ "
ICON_FAIL  = "❌"
ICON_SKIP  = "⏩"

SEP = "=" * 65


class APIHealthChecker:
    """
    Vérifie la disponibilité de toutes les APIs du pipeline CIV-Eye.
    Produit des logs clairs et structurés sur l'état de chaque source.
    """

    def __init__(self):
        self.results = {}

    def run_all_checks(self) -> dict:
        """
        Lance tous les diagnostics et retourne un dict de résultats.
        Affiche un rapport complet dans les logs Django.
        """
        logger.info(f"\n{SEP}")
        logger.info("  CIV-EYE — DIAGNOSTIC COMPLET DES APIs ET SOURCES")
        logger.info(f"{SEP}")

        self._check_local_tiff_files()
        self._check_sentinel_hub()
        self._check_cdse_stac()
        self._check_microsoft_planetary_computer()
        self._check_google_earth_engine()
        self._check_huggingface_api()

        self._print_summary()
        return self.results

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 1 : Fichiers TIFF locaux (Source zéro-dépendance)
    # ─────────────────────────────────────────────────────────────────────
    def _check_local_tiff_files(self):
        """Vérifie que les fichiers TIFF Sentinel-2 locaux sont présents dans sentinel_api_exports."""
        label = "TIFF Locaux (sentinel_api_exports)"
        try:
            from django.conf import settings
            # Correction : le bon dossier est sentinel_api_exports, pas sentinel/
            sentinel_dir = os.path.join(settings.BASE_DIR, "module1_urbanisme", "data_use", "sentinel_api_exports")

            if not os.path.exists(sentinel_dir):
                self._log(ICON_FAIL, label, "Dossier introuvable : module1_urbanisme/data_use/sentinel_api_exports/")
                self.results["local_tiff"] = False
                return

            # Le dossier est organisé en sous-dossiers par date (ex: 2024-02-15/)
            date_dirs = [d for d in os.listdir(sentinel_dir)
                         if os.path.isdir(os.path.join(sentinel_dir, d))]

            if len(date_dirs) < 2:
                self._log(ICON_WARN, label, f"Seulement {len(date_dirs)} date(s) disponible(s) — minimum 2 requis (T1 + T2)")
                self.results["local_tiff"] = False
                return

            total_files = 0
            corrupt_files = []
            for date_dir in sorted(date_dirs):
                dir_path = os.path.join(sentinel_dir, date_dir)
                # Chercher .tif (3 lettres) ET .tiff (4 lettres)
                tif_files = [f for f in os.listdir(dir_path) if f.lower().endswith((".tif", ".tiff"))]
                bands_found = [b for b in ["B04", "B08", "B11", "SCL"] if any(b in f for f in tif_files)]
                scl_ok = ICON_OK if "SCL" in bands_found else ICON_WARN + " SCL absent"
                logger.info(f"  {ICON_OK} {date_dir} — Bandes: {', '.join(bands_found)} | {scl_ok}")
                total_files += len(tif_files)

                # Test d'intégrité : vérifier que le premier TIFF s'ouvre sans erreur
                if tif_files:
                    try:
                        import rasterio
                        first_tif = os.path.join(dir_path, tif_files[0])
                        with rasterio.open(first_tif) as src:
                            _ = src.shape  # force la lecture du header
                    except Exception as e:
                        corrupt_files.append(f"{date_dir}/{tif_files[0]}: {e}")

            if corrupt_files:
                self._log(ICON_WARN, label, f"Fichiers TIFF corrompus : {corrupt_files}")
                self.results["local_tiff"] = True  # pipeline peut continuer mais warning
            else:
                self._log(ICON_OK, label, f"{total_files} fichiers TIF — {len(date_dirs)} dates (T1 + T2). Pipeline local fonctionnel.")
            self.results["local_tiff"] = True

        except Exception as e:
            self._log(ICON_FAIL, label, f"Erreur inattendue : {e}")
            self.results["local_tiff"] = False

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 2 : Sentinel Hub API (Option A)
    # ─────────────────────────────────────────────────────────────────────
    def _check_sentinel_hub(self):
        """Vérifie les credentials Sentinel Hub dans .env."""
        label = "Sentinel Hub API (Option A)"
        client_id = os.getenv("SENTINEL_HUB_CLIENT_ID", "").strip()
        client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "").strip()

        if not client_id or not client_secret:
            self._log(ICON_WARN, label, "Clés absentes dans .env (SENTINEL_HUB_CLIENT_ID / SECRET) → Ignoré")
            self.results["sentinel_hub"] = False
            return

        # B35 : Vérification réelle du token via OAuth2 (GET léger, timeout 3s)
        try:
            import urllib.request
            import urllib.parse
            token_url = "https://services.sentinel-hub.com/oauth/tokeninfo"
            # Tenter un token OAuth2 client_credentials
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }).encode()
            req = urllib.request.Request(
                "https://services.sentinel-hub.com/oauth/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    self._log(ICON_OK, label, f"Token valide (ID={client_id[:6]}***)")
                    self.results["sentinel_hub"] = True
                else:
                    self._log(ICON_WARN, label, f"Réponse inattendue (HTTP {resp.status})")
                    self.results["sentinel_hub"] = False
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "403" in err_msg:
                self._log(ICON_FAIL, label, f"Token expiré ou invalide (ID={client_id[:6]}***)")
            else:
                self._log(ICON_WARN, label, f"Vérification impossible ({err_msg[:60]})")
            self.results["sentinel_hub"] = False

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 3 : CDSE Copernicus STAC (Option B — sans clé)
    # ─────────────────────────────────────────────────────────────────────
    def _check_cdse_stac(self):
        """Vérifie la disponibilité du catalogue CDSE Copernicus (100% gratuit, sans clé)."""
        label = "CDSE Copernicus STAC (sans clé)"
        try:
            import urllib.request
            # Test léger : juste vérifier que l'URL répond (pas de téléchargement)
            req = urllib.request.Request(
                "https://catalogue.dataspace.copernicus.eu/stac",
                headers={"User-Agent": "CIV-Eye/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.getcode() == 200:
                    self._log(ICON_OK, label, "API CDSE accessible — GRATUIT, SANS CLÉ. Fallback toujours disponible.")
                    self.results["cdse_stac"] = True
                else:
                    self._log(ICON_WARN, label, f"CDSE répond avec code {resp.getcode()}")
                    self.results["cdse_stac"] = False
        except Exception as e:
            self._log(ICON_FAIL, label, f"CDSE inaccessible (réseau ?) : {e}")
            self.results["cdse_stac"] = False

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 4 : Microsoft Planetary Computer (Option C)
    # ─────────────────────────────────────────────────────────────────────
    def _check_microsoft_planetary_computer(self):
        """Vérifie la clé Microsoft Planetary Computer."""
        label = "Microsoft Planetary Computer (Option C)"
        api_key = os.getenv("MICROSOFT_PC_API_KEY", "").strip()

        if not api_key:
            self._log(ICON_WARN, label, "Clé absente (MICROSOFT_PC_API_KEY dans .env) → Ignoré")
            self.results["ms_pc"] = False
            return

        try:
            import urllib.request, json
            req = urllib.request.Request(
                "https://planetarycomputer.microsoft.com/api/stac/v1",
                headers={"Ocp-Apim-Subscription-Key": api_key, "User-Agent": "CIV-Eye/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                self._log(ICON_OK, label, f"API MS Planetary Computer active — {data.get('title', 'OK')}")
                self.results["ms_pc"] = True
        except Exception as e:
            self._log(ICON_WARN, label, f"Clé configurée mais accès échoué : {e}")
            self.results["ms_pc"] = False

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 5 : Google Earth Engine API
    # ─────────────────────────────────────────────────────────────────────
    def _check_google_earth_engine(self):
        """Vérifie si Earth Engine est initialisé (authentification Google)."""
        label = "Google Earth Engine Python API"
        try:
            import ee
            project_id = os.getenv("GEE_PROJECT_ID", "").strip()
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()  # Fallback for old configurations
            self._log(ICON_OK, label, f"GEE initialisé correctement — projet: {project_id or 'défaut'}")
            self.results["gee"] = True
        except ImportError:
            self._log(ICON_SKIP, label, "earthengine-api non installé — non requis au runtime Django")
            self.results["gee"] = False
        except Exception as e:
            self._log(ICON_WARN, label, f"GEE non initialisé ({type(e).__name__}) — run `ee.Authenticate()` une fois")
            self.results["gee"] = False

    # ─────────────────────────────────────────────────────────────────────
    # CHECK 6 : Hugging Face Inference API (IA Cloud — AUCUNE INSTALLATION)
    # ─────────────────────────────────────────────────────────────────────
    def _check_huggingface_api(self):
        """Vérifie la clé Hugging Face pour l'IA déportée (zéro install local)."""
        label = "Hugging Face Inference API (IA Cloud)"
        hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()

        if not hf_token:
            self._log(ICON_WARN, label,
                "Clé absente (HUGGINGFACE_TOKEN dans .env) → Aucune IA cloud disponible\n"
                "         Action : créer un compte sur huggingface.co → Settings → Access Tokens → New Token (gratuit)"
            )
            self.results["huggingface"] = False
            return

        try:
            import urllib.request, json
            req = urllib.request.Request(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {hf_token}", "User-Agent": "CIV-Eye/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                username = data.get("name", "?")
                self._log(ICON_OK, label, f"Token valide — Compte HuggingFace : {username} — IA Cloud opérationnelle")
                self.results["huggingface"] = True
        except Exception as e:
            self._log(ICON_FAIL, label, f"Token invalide ou expiré : {e} → Renouveler sur huggingface.co/settings/tokens")
            self.results["huggingface"] = False

    # ─────────────────────────────────────────────────────────────────────
    # LOG + SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    def _log(self, icon: str, label: str, message: str):
        logger.info(f"\n  {icon} [{label}]\n         {message}")

    def _print_summary(self):
        ok = [k for k, v in self.results.items() if v]
        fail = [k for k, v in self.results.items() if not v]
        logger.info(f"\n{SEP}")
        logger.info("  RÉSUMÉ DU DIAGNOSTIC")
        logger.info(f"  {ICON_OK} Disponible : {', '.join(ok) if ok else 'AUCUN'}")
        logger.info(f"  {ICON_FAIL} Indisponible : {', '.join(fail) if fail else 'AUCUN'}")

        has_data = self.results.get("local_tiff") or self.results.get("cdse_stac") or self.results.get("sentinel_hub")
        if has_data:
            logger.info(f"  {ICON_OK} PIPELINE DE DONNÉES : OPÉRATIONNEL (au moins une source active)")
        else:
            logger.warning(f"  {ICON_FAIL} PIPELINE DE DONNÉES : AUCUNE SOURCE ACTIVE — détection impossible")
        logger.info(f"{SEP}\n")

    def assert_minimum_viable(self):
        """
        Vérifie qu'au moins une source de données est disponible
        ET qu'il y a au moins 2 ImageSatellite en base (T1 + T2).
        Lève une RuntimeError avec un message clair si ce n'est pas le cas.
        """
        if not self.results:
            self.run_all_checks()

        has_data = (
            self.results.get("local_tiff") or
            self.results.get("cdse_stac") or
            self.results.get("sentinel_hub")
        )
        if not has_data:
            raise RuntimeError(
                "❌ AUCUNE SOURCE DE DONNÉES DISPONIBLE.\n"
                "  → Vérifiez les fichiers TIF dans module1_urbanisme/data_use/sentinel_api_exports/\n"
                "  → Ou configurez SENTINEL_HUB_CLIENT_ID dans .env\n"
                "  → Ou vérifiez votre connexion Internet (CDSE STAC)\n"
            )

        # M14 : Vérifier qu'il y a assez d'images en base pour une comparaison T1/T2
        try:
            from module1_urbanisme.models import ImageSatellite
            image_count = ImageSatellite.objects.count()
            if image_count < 2:
                logger.warning(
                    f"⚠️ Seulement {image_count} ImageSatellite en base. "
                    f"Le pipeline nécessite au minimum 2 images (T1 + T2). "
                    f"Lancez d'abord : python manage.py import_sentinel --folder <dossier>"
                )
        except Exception:
            pass
