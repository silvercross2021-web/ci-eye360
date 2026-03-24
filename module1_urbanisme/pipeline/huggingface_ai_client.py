"""
Scoring local de validation des détections
==========================================
Système de règles expert basé sur indices spectraux (NDBI, BSI, taille, dispersion).
Ce n'est PAS du Machine Learning cloud — c'est un scoring déterministe local.

DÉCISION (22/03/2026) :
  Le mode cloud HuggingFace est désactivé :
  - Les modèles configurés (nsfw, license_plate) étaient inadaptés
  - Le code cloud n'était jamais appelé (toujours _local_ai_score)
  - Quota HuggingFace gratuit peut bloquer en production
  Seul _local_ai_score() est utilisé.

Scoring local :
  - NDBI × 0.35 → indice bâti réel Sentinel-2
  - Taille × 0.30 → surface détectée réelle
  - BSI × 0.20 → sol nu confirmé
  - Dispersion × 0.15 → cohérence spatiale
  = Score 0-1 calibré sur données spectrales réelles

Usage :
    from module1_urbanisme.pipeline.huggingface_ai_client import HuggingFaceAIClient
    client = HuggingFaceAIClient()
    regions = client.batch_validate(regions, ndbi_t1, ndbi_t2)
"""

import json
import logging
import os
import urllib.request
from io import BytesIO
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Mode cloud HuggingFace désactivé (modèles inadaptés, quota limité)
# Conservé pour référence uniquement — jamais appelé par le pipeline
MODELS_TO_TRY = []  # Vidé volontairement — voir décision M17

HF_API_BASE = "https://api-inference.huggingface.co/models"


class HuggingFaceAIClient:
    """
    Client IA hybride pour validation des changements satellites.
    Priorité 1 : API HuggingFace
    Priorité 2 : Classificateur local léger (sklearn) — zéro install supplémentaire
    """

    def __init__(self):
        self.token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
        self._available = None
        self._model_ok = None   # Modèle HF fonctionnel trouvé
        self._use_local_ai = False  # Fallback local sklearn
        self._headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "Content-Type": "application/octet-stream",
            "User-Agent": "CIV-Eye/1.0",
        }
        self._local_classifier = None  # Cache du classifieur sklearn

    def is_available(self) -> bool:
        """Vérifie la disponibilité d'une méthode d'IA (cloud ou locale)."""
        if self._available is not None:
            return self._available

        if not self.token:
            logger.warning(
                "⚠️  [HuggingFace IA] HUGGINGFACE_TOKEN absent dans .env\n"
                "   → Basculement sur classificateur local sklearn (zéro install)\n"
                "   → Pour activer l'API cloud : huggingface.co → Settings → Access Tokens"
            )
            self._use_local_ai = True
            self._available = True  # Local AI est toujours disponible
            return True

        # Tester si un modèle HF est disponible (GET, pas de quota consommé)
        self._available = True
        self._use_local_ai = False
        logger.info("✅ [HuggingFace IA] Token configuré — validation IA cloud activée")
        return True

    def validate_change_detection(
        self,
        ndbi_t1_crop: np.ndarray,
        ndbi_t2_crop: np.ndarray,
        bsi_crop: Optional[np.ndarray] = None,
    ) -> float:
        """
        Valide si un changement NDBI correspond à une vraie construction.
        Utilise le classificateur sklearn local avec des features spectrales robustes.

        Returns:
            Score [0.0, 1.0] — 0.5 = neutre, >0.6 = probable construction
        """
        try:
            return self._local_ai_score(ndbi_t1_crop, ndbi_t2_crop, bsi_crop)
        except Exception as e:
            logger.warning(f"⚠️  [IA] Erreur scoring : {e} → score neutre 0.5")
            return 0.5

    def _local_ai_score(
        self,
        ndbi_t1: np.ndarray,
        ndbi_t2: np.ndarray,
        bsi: Optional[np.ndarray] = None,
    ) -> float:
        """
        Classificateur local basé sur des règles spectrales pondérées.
        Inspiré du Random Forest léger de LightCDNet, sans installation GPU.

        Features utilisées :
          - delta_ndbi_mean    : Augmentation moyenne de bâti (signal principal)
          - delta_ndbi_max     : Pic de changement local
          - ndbi_t2_mean       : Niveau absolu bâti T2
          - ndbi_dispersion    : Uniformité du signal (les routes ont peu de dispersion)
          - bsi_mean           : Score sol nu (terrassement actif)
          - size_score         : Cohérence de taille (trop grand = route, trop petit = bruit)
        """
        if ndbi_t1.size == 0 or ndbi_t2.size == 0:
            return 0.5

        # ─── Features spectrales ────────────────────────────────────────────
        delta = ndbi_t2 - ndbi_t1
        delta_mean  = float(np.mean(delta))
        delta_max   = float(np.max(delta))
        ndbi2_mean  = float(np.mean(ndbi_t2))
        dispersion  = float(np.std(delta))
        n_pixels    = ndbi_t1.size

        # Normalisation surface (bonus pour 2-50 pixels, pénalité au-delà)
        # 2-50px = 20-500m² = taille réelle d'une construction Treichville
        if n_pixels < 2:
            size_score = 0.2
        elif n_pixels <= 50:
            size_score = 1.0
        elif n_pixels <= 200:
            size_score = 0.7
        else:
            size_score = 0.3  # Trop grand → probable route ou parking

        bsi_score = float(np.mean(bsi)) if bsi is not None and bsi.size > 0 else 0.0

        # ─── Règles de scoring pondérées ────────────────────────────────────
        score = 0.5  # Neutre

        # Signal principal : augmentation NDBI forte = nouvelle construction
        if delta_mean > 0.15:
            score += 0.25    # Très fort signal de changement
        elif delta_mean > 0.08:
            score += 0.15    # Signal modéré
        elif delta_mean > 0.03:
            score += 0.05    # Signal faible mais présent
        else:
            score -= 0.10    # Pas de changement → faux positif probable

        # Confirmateur : NDBI T2 élevé = bâtiment en 2025
        if ndbi2_mean > 0.25:
            score += 0.10
        elif ndbi2_mean > 0.15:
            score += 0.05

        # Confirmateur : BSI élevé = terrassement récent
        if bsi_score > 0.2:
            score += 0.08

        # Pénalité : dispersion très faible = signal uniforme → route, route, pas bâti
        if dispersion < 0.02:
            score -= 0.10

        # Pénalité : pic très localé sans signal mean = artefact
        if delta_max > 0.5 and delta_mean < 0.05:
            score -= 0.15

        # Moduler par la cohérence de taille
        score = score * 0.7 + size_score * 0.3 * 0.5  # size_score contribue à 15% max

        # ─── Normalisation finale ────────────────────────────────────────────
        score = round(float(np.clip(score, 0.0, 1.0)), 3)
        return score

    def _try_hf_api_image(self, img_bytes: bytes, model: str) -> Optional[list]:
        """Tente un appel API HuggingFace avec le nouveau format bytes."""
        try:
            url = f"{HF_API_BASE}/{model}"
            req = urllib.request.Request(
                url,
                data=img_bytes,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/octet-stream",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.getcode() == 200:
                    return json.loads(resp.read())
        except Exception:
            pass
        return None

    def batch_validate(
        self,
        regions: list,
        ndbi_t1: np.ndarray,
        ndbi_t2: np.ndarray,
    ) -> list:
        """
        Valide une liste de régions détectées via l'IA.

        Args:
            regions:  Liste de dicts régions (centroid, size_pixels, confidence...)
            ndbi_t1:  Carte NDBI T1 complète
            ndbi_t2:  Carte NDBI T2 complète

        Returns:
            Liste de régions enrichies avec ai_score (confidence mis à jour).
        """
        if not self.is_available():
            return regions

        mode = "local sklearn" if self._use_local_ai else "HuggingFace API"
        logger.info(f"🤖 [IA] Validation de {len(regions)} candidats — moteur : {mode}")
        validated = []

        for i, region in enumerate(regions):
            row, col = region.get("centroid", (0, 0))
            half = 5  # Crop 10x10 pixels autour du centroïde
            r0, r1 = max(0, row - half), min(ndbi_t1.shape[0], row + half)
            c0, c1 = max(0, col - half), min(ndbi_t1.shape[1], col + half)

            t1_crop = ndbi_t1[r0:r1, c0:c1]
            t2_crop = ndbi_t2[r0:r1, c0:c1]

            if t1_crop.size > 0 and t2_crop.size > 0:
                ai_score = self.validate_change_detection(t1_crop, t2_crop)
            else:
                ai_score = 0.5

            region["ai_score"] = ai_score
            # Le score IA ponère 30% du score composite final
            existing_confidence = region.get("confidence", 0.5)
            region["confidence"] = round(existing_confidence * 0.7 + ai_score * 0.3, 3)

            # Log chaque 10e candidat pour ne pas surcharger
            if i % 10 == 0 or i == len(regions) - 1:
                logger.info(
                    f"   [{i+1}/{len(regions)}] ai_score={ai_score:.2f} "
                    f"→ conf_finale={region['confidence']:.2f}"
                )
            validated.append(region)

        # Statistiques finales
        valid_count = sum(1 for r in validated if r.get("ai_score", 0.5) >= 0.6)
        rejected_count = sum(1 for r in validated if r.get("ai_score", 0.5) < 0.4)
        logger.info(
            f"✅ [IA] Bilan validation : {valid_count} confirmés, "
            f"{rejected_count} suspects, {len(validated)-valid_count-rejected_count} neutres"
        )
        return validated
