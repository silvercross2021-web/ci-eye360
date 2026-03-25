"""
Acquisition automatique des données Sentinel-2 — Phase 3
Module 1 Urbanisme - CIV-Eye

Remplace le chargement manuel des TIFF par 3 options en cascade :
  Option A : Sentinel Hub API  (credentials .env)         ← priorité 1
  Option B : CDSE Copernicus STAC (sans inscription)     ← fallback gratuit
  Option C : Microsoft Planetary Computer (.env key opt) ← fallback 2

Usage :
    from module1_urbanisme.pipeline.sentinel_data_fetcher import SentinelDataFetcher
    fetcher = SentinelDataFetcher()
    bands = fetcher.get_bands_for_date("2024-01-29", ["B04", "B08", "B11"])
    # → retourne {"B04": np.ndarray, "B08": np.ndarray, "B11": np.ndarray}
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Coordonnées Treichville / Abidjan (BBOX WGS84)
TREICHVILLE_BBOX = {
    "min_lon": -4.03001,
    "min_lat":  5.28501,
    "max_lon": -3.97301,
    "max_lat":  5.32053,
}

# Résolution en mètres des bandes Sentinel-2
BAND_RESOLUTION = {
    "B02": 10, "B03": 10, "B04": 10, "B08": 10,
    "B05": 20, "B06": 20, "B07": 20, "B11": 20, "B12": 20,
    "SCL": 20,
}


class SentinelDataFetcher:
    """
    Fetcher multi-source pour les données Sentinel-2.
    Sélectionne automatiquement la meilleure source disponible.
    """

    def __init__(self):
        self._sh_config = None
        self._sh_available = False
        self._cdse_available = True   # toujours disponible (API publique)
        self._pc_available = False

        # Tenter d'initialiser Sentinel Hub
        self._init_sentinel_hub()
        # Tenter d'initialiser Planetary Computer
        self._init_planetary_computer()

    # ─────────────────────────────────────────────────────────────────────
    # INIT SOURCES
    # ─────────────────────────────────────────────────────────────────────
    def _init_sentinel_hub(self):
        """Initialise la configuration Sentinel Hub depuis les variables d'environnement."""
        try:
            from sentinelhub import SHConfig
            client_id     = os.getenv("SENTINEL_HUB_CLIENT_ID", "").strip()
            client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "").strip()

            if not client_id or not client_secret:
                logger.info("Sentinel Hub : clés non configurées dans .env → option ignorée")
                return

            config = SHConfig()
            config.sh_client_id     = client_id
            config.sh_client_secret = client_secret
            config.sh_base_url      = "https://services.sentinel-hub.com"

            self._sh_config   = config
            self._sh_available = True
            logger.info("Sentinel Hub : configuration OK")

        except ImportError:
            logger.warning("sentinelhub non installé — pip install sentinelhub")
        except Exception as e:
            logger.warning(f"Sentinel Hub init échouée : {e}")

    def _init_planetary_computer(self):
        """Vérifie la disponibilité de Microsoft Planetary Computer."""
        try:
            import planetary_computer  # noqa
            import pystac_client       # noqa
            self._pc_available = True
            logger.info("Microsoft Planetary Computer : disponible")
        except ImportError:
            logger.info("planetary-computer non installé → ignoré")

    # ─────────────────────────────────────────────────────────────────────
    # API PRINCIPALE
    # ─────────────────────────────────────────────────────────────────────
    def get_bands_for_date(
        self,
        target_date: str,
        bands: List[str] = None,
        bbox: Optional[Dict] = None,
        max_cloud_cover: float = 20.0,
        date_window_days: int = 15,
    ) -> Dict[str, np.ndarray]:
        """
        Récupère les bandes Sentinel-2 pour une date donnée.

        Essaie les sources dans l'ordre : Sentinel Hub → CDSE → Planetary Computer.
        Sélectionne automatiquement l'image avec le moins de nuages dans
        la fenêtre [target_date - date_window_days, target_date + date_window_days].

        Args:
            target_date:      Date cible au format "YYYY-MM-DD"
            bands:            Liste de bandes ex. ["B04", "B08", "B11", "SCL"]
            bbox:             Zone géographique (défaut: Treichville)
            max_cloud_cover:  Couverture nuageuse max acceptée (%)
            date_window_days: Fenêtre de recherche avant/après la date cible

        Returns:
            Dict {band_name: np.ndarray} — tableaux 2D float32.
        """
        if bands is None:
            bands = ["B04", "B08", "B11", "SCL"]
        if bbox is None:
            bbox = TREICHVILLE_BBOX

        logger.info(
            f"Fetching Sentinel-2 | date={target_date} | bandes={bands} | "
            f"cloud<{max_cloud_cover}% | window=±{date_window_days}j"
        )

        # ── Option A : Sentinel Hub ──────────────────────────────────────
        if self._sh_available:
            try:
                result = self._fetch_sentinel_hub(
                    target_date, bands, bbox, max_cloud_cover, date_window_days
                )
                if result:
                    logger.info("Source utilisée : Sentinel Hub API ✓")
                    return result
            except Exception as e:
                logger.warning(f"Sentinel Hub fetch échoué : {e}")

        # ── Option B : CDSE Copernicus (sans clé) ────────────────────────
        try:
            result = self._fetch_cdse(
                target_date, bands, bbox, max_cloud_cover, date_window_days
            )
            if result:
                logger.info("Source utilisée : CDSE Copernicus STAC ✓")
                return result
        except Exception as e:
            logger.warning(f"CDSE fetch échoué : {e}")

        # ── Option C : Microsoft Planetary Computer ──────────────────────
        if self._pc_available:
            try:
                result = self._fetch_planetary_computer(
                    target_date, bands, bbox, max_cloud_cover, date_window_days
                )
                if result:
                    logger.info("Source utilisée : Microsoft Planetary Computer ✓")
                    return result
            except Exception as e:
                logger.warning(f"Planetary Computer fetch échoué : {e}")

        raise RuntimeError(
            f"Impossible de récupérer les bandes Sentinel-2 pour {target_date}. "
            f"Vérifiez les credentials dans .env ou la connexion internet."
        )

    # ─────────────────────────────────────────────────────────────────────
    # OPTION A : SENTINEL HUB
    # ─────────────────────────────────────────────────────────────────────
    def _fetch_sentinel_hub(
        self,
        target_date: str,
        bands: List[str],
        bbox: Dict,
        max_cloud_cover: float,
        date_window_days: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """Fetch via Sentinel Hub Process API avec mosaïque anti-nuage."""
        from sentinelhub import (
            BBox, CRS, DataCollection, SentinelHubRequest,
            MimeType, bbox_to_dimensions, MosaickingOrder,
        )

        sh_bbox = BBox(
            bbox=(bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]),
            crs=CRS.WGS84,
        )

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        time_interval = (
            (dt - timedelta(days=date_window_days)).strftime("%Y-%m-%d"),
            (dt + timedelta(days=date_window_days)).strftime("%Y-%m-%d"),
        )

        # Evalscript : calcule la MÉDIANE sur la période pour ignorer les nuages
        band_list   = [b for b in bands if b != "SCL"]
        has_scl     = "SCL" in bands
        input_bands = band_list + (["SCL"] if has_scl else [])

        evalscript = f"""
        //VERSION=3
        function setup() {{
            return {{
                input: [{{ bands: {str(input_bands).replace("'", '"')}, units: "DN" }}],
                output: {{ bands: {len(input_bands)}, sampleType: "FLOAT32" }},
                mosaicking: "ORBIT"
            }};
        }}

        function evaluatePixel(samples) {{
            // On filtre les échantillons pour ne garder que ceux qui ne sont pas des nuages
            // SCL: 8 (Cloud medium prob), 9 (Cloud high prob), 10 (Thin cirrus), 3 (Cloud shadow)
            let validSamples = samples.filter(s => s.SCL !== 8 && s.SCL !== 9 && s.SCL !== 10 && s.SCL !== 3 && s.SCL !== 0);
            
            // Si aucun échantillon n'est parfait, on prend tous les échantillons sauf le noir total
            if (validSamples.length === 0) {{
                validSamples = samples.filter(s => s.SCL !== 0);
            }}
            if (validSamples.length === 0) return new Array({len(input_bands)}).fill(0);

            let result = [];
            let b_names = {str(input_bands).replace("'", '"')};
            
            for (let b of b_names) {{
                let values = validSamples.map(s => s[b]).sort((a, b) => a - b);
                let median = values[Math.floor(values.length / 2)];
                result.push(median);
            }}
            return result;
        }}
        """

        resolution = 10
        size = bbox_to_dimensions(sh_bbox, resolution=resolution)

        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=time_interval,
                    mosaicking_order=MosaickingOrder.LEAST_CC, 
                    maxcc=max_cloud_cover / 100.0,
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            bbox=sh_bbox,
            size=size,
            config=self._sh_config,
        )

        data = request.get_data()[0]  # shape: (H, W, N_bands)
        if data is None or data.size == 0:
            return None

        result = {}
        for i, band_name in enumerate(input_bands):
            arr = data[:, :, i].astype(np.float32)
            # Normaliser les réflectances DN → [0,1] si pas SCL
            if band_name != "SCL":
                arr = np.where(arr > 0, arr / 10000.0, 0.0)
            result[band_name] = arr

        return result

    # ─────────────────────────────────────────────────────────────────────
    # OPTION B : CDSE Copernicus STAC (sans clé)
    # ─────────────────────────────────────────────────────────────────────
    def _fetch_cdse(
        self,
        target_date: str,
        bands: List[str],
        bbox: Dict,
        max_cloud_cover: float,
        date_window_days: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Fetch via le catalogue STAC public de Copernicus Data Space.
        Aucune clé requise. 100% gratuit.
        URL: https://catalogue.dataspace.copernicus.eu/stac
        """
        import pystac_client
        import rasterio
        from rasterio.windows import from_bounds

        catalog = pystac_client.Client.open(
            "https://catalogue.dataspace.copernicus.eu/stac"
        )

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        time_from = (dt - timedelta(days=date_window_days)).strftime("%Y-%m-%dT00:00:00Z")
        time_to   = (dt + timedelta(days=date_window_days)).strftime("%Y-%m-%dT23:59:59Z")

        bbox_list = [
            bbox["min_lon"], bbox["min_lat"],
            bbox["max_lon"], bbox["max_lat"],
        ]

        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox_list,
            datetime=f"{time_from}/{time_to}",
            max_items=10,
        )

        items = list(search.items())
        if not items:
            logger.warning(f"CDSE : aucune image trouvée pour {target_date} (cloud<{max_cloud_cover}%)")
            return None

        # Prendre l'image avec le moins de nuages
        items.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
        best_item = items[0]
        cloud_pct = best_item.properties.get("eo:cloud_cover", "?")
        logger.info(
            f"CDSE : meilleure image trouvée — "
            f"date={best_item.datetime.strftime('%Y-%m-%d')}, "
            f"cloud={cloud_pct}%"
        )

        CDSE_BAND_MAP = {
            "B02": "B02", "B03": "B03", "B04": "B04",
            "B08": "B08", "B11": "B11", "B12": "B12",
            "SCL": "SCL",
        }

        result = {}
        for band_name in bands:
            asset_key = CDSE_BAND_MAP.get(band_name)
            if not asset_key or asset_key not in best_item.assets:
                logger.warning(f"CDSE : bande {band_name} non trouvée dans l'item")
                continue

            href = best_item.assets[asset_key].href
            try:
                with rasterio.open(href) as src:
                    window = from_bounds(
                        bbox["min_lon"], bbox["min_lat"],
                        bbox["max_lon"], bbox["max_lat"],
                        transform=src.transform,
                    )
                    arr = src.read(1, window=window).astype(np.float32)
                    # Normaliser réflectances
                    if band_name != "SCL":
                        arr = np.where(arr > 0, arr / 10000.0, 0.0)
                    result[band_name] = arr
                    logger.info(f"CDSE : bande {band_name} récupérée — shape={arr.shape}")
            except Exception as e:
                logger.warning(f"CDSE : erreur lecture bande {band_name} : {e}")

        return result if result else None

    # ─────────────────────────────────────────────────────────────────────
    # OPTION C : Microsoft Planetary Computer
    # ─────────────────────────────────────────────────────────────────────
    def _fetch_planetary_computer(
        self,
        target_date: str,
        bands: List[str],
        bbox: Dict,
        max_cloud_cover: float,
        date_window_days: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """Fetch via Microsoft Planetary Computer (STAC + COG)."""
        import planetary_computer
        import pystac_client
        import rasterio
        from rasterio.windows import from_bounds

        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        time_from = (dt - timedelta(days=date_window_days)).strftime("%Y-%m-%d")
        time_to   = (dt + timedelta(days=date_window_days)).strftime("%Y-%m-%d")
        bbox_list  = [bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]]

        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox_list,
            datetime=f"{time_from}/{time_to}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
            sortby="eo:cloud_cover",
        )

        items = list(search.items())
        if not items:
            return None

        best_item = items[0]
        logger.info(
            f"PC : image {best_item.id} — "
            f"cloud={best_item.properties.get('eo:cloud_cover', '?')}%"
        )

        PC_BAND_MAP = {
            "B02": "B02", "B03": "B03", "B04": "B04",
            "B08": "B08", "B11": "B11", "B12": "B12",
            "SCL": "SCL",
        }

        result = {}
        signed_item = planetary_computer.sign(best_item)
        for band_name in bands:
            asset_key = PC_BAND_MAP.get(band_name)
            if not asset_key or asset_key not in signed_item.assets:
                continue
            href = signed_item.assets[asset_key].href
            try:
                with rasterio.open(href) as src:
                    window = from_bounds(
                        bbox["min_lon"], bbox["min_lat"],
                        bbox["max_lon"], bbox["max_lat"],
                        transform=src.transform,
                    )
                    arr = src.read(1, window=window).astype(np.float32)
                    if band_name != "SCL":
                        arr = np.where(arr > 0, arr / 10000.0, 0.0)
                    result[band_name] = arr
            except Exception as e:
                logger.warning(f"PC : erreur bande {band_name} : {e}")

        return result if result else None

    # ─────────────────────────────────────────────────────────────────────
    # API HAUT NIVEAU : récupère T1 et T2 prêts pour le pipeline
    # ─────────────────────────────────────────────────────────────────────
    def get_t1_and_t2_bands(
        self,
        date_t1: str,
        date_t2: str,
        bands: List[str] = None,
        max_cloud_cover: float = 15.0,
    ) -> tuple:
        """
        Récupère les bandes de T1 et T2 prêtes pour le pipeline NDBI.

        Args:
            date_t1: Date T1 au format 'YYYY-MM-DD' (obligatoire)
            date_t2: Date T2 au format 'YYYY-MM-DD' (obligatoire)

        Returns:
            Tuple (bands_t1_dict, bands_t2_dict) chacun étant un dict {band: np.ndarray}

        Raises:
            ValueError: si date_t1 ou date_t2 est absent ou vide
        """
        if not date_t1 or not date_t2:
            raise ValueError(
                "get_t1_and_t2_bands : date_t1 et date_t2 sont obligatoires. "
                "Exemple : fetcher.get_t1_and_t2_bands('2024-02-15', '2025-01-15')"
            )
        if bands is None:
            bands = ["B04", "B08", "B11", "SCL"]

        logger.info(f"Récupération T1 ({date_t1}) et T2 ({date_t2})...")
        bands_t1 = self.get_bands_for_date(date_t1, bands, max_cloud_cover=max_cloud_cover)
        bands_t2 = self.get_bands_for_date(date_t2, bands, max_cloud_cover=max_cloud_cover)
        return bands_t1, bands_t2

    # ─────────────────────────────────────────────────────────────────────
    # DIAGNOSTIC
    # ─────────────────────────────────────────────────────────────────────
    def status(self) -> Dict:
        """Retourne l'état des sources disponibles."""
        return {
            "sentinel_hub":          self._sh_available,
            "cdse_copernicus":       self._cdse_available,
            "planetary_computer":    self._pc_available,
            "active_source": (
                "sentinel_hub"       if self._sh_available else
                "cdse_copernicus"    if self._cdse_available else
                "planetary_computer" if self._pc_available else
                "none"
            ),
        }
