"""
Détecteur IA Deep Learning (PyTorch) — MODE EXPÉRIMENTAL
=========================================================
Réseau de neurones siamois TinyCD pour la détection de changement de bâtiments.

⚠️ AVERTISSEMENT :
  Les poids disponibles (levir_best.pth) ont été entraînés sur des images
  aériennes 0.5m/pixel (villes américaines/chinoises), soit 20x plus précises
  que Sentinel-2 (10m/pixel). Les matériaux (villas USA, entrepôts) diffèrent
  des constructions de Treichville (tôle, béton brut, terre battue).
  → Précision non garantie sur données africaines Sentinel-2.
  → Utiliser NDBI (défaut) ou K-Means (--use-ai) comme méthodes de référence.

Prérequis :
 - PyTorch (pip install torch torchvision)
 - Le fichier de poids model_weights.pth (levir_best.pth renommé) dans data_use/weights/
   Source : https://github.com/AndreaCodegoni/Tiny_model_4_CD/tree/main/pretrained_models
"""

import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# B33 — Seuil de détection TinyCD.
# Abaissé à 0.30 (vs 0.50 original LEVIR-CD) pour contexte africain Sentinel-2 10m/px.
# ⚠️ Non validé sur vérité terrain ivoirienne — calibrer avec données GPS Treichville.
TINYCD_CHANGE_THRESHOLD = 0.30

class DeepLearningDetector:
    def __init__(self, model_version="tinycd"):
        self.model_version = model_version
        # BUG-008 : Utiliser settings.BASE_DIR pour éviter les erreurs de chemin relatif
        from django.conf import settings
        self.weights_path = os.path.join(
            settings.BASE_DIR, "module1_urbanisme", "data_use", "weights", "model_weights.pth"
        )
        self.is_ready = False
        self.model = None

        try:
            import torch
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"🧠 [Deep Learning] Initialisation sur {self.device}...")
            
            # Vérification de la présence des poids
            if os.path.exists(self.weights_path):
                self._load_model(torch)
                self.is_ready = True
            else:
                logger.warning(
                    f"⚠️ [Deep Learning] Le fichier de poids est INTROUVABLE : {self.weights_path}\n"
                    "👉 Vous devez télécharger le fichier .pth de TinyCD (ou Siam-UNet) et le renommer en 'model_weights.pth' dans le dossier data_use/weights/"
                )
        except ImportError:
            logger.error("❌ [Deep Learning] PyTorch n'est pas installé correctement.")

    def _load_model(self, torch):
        """Charge l'architecture mathématique et les poids de TinyCD."""
        logger.info(f"🔄 Chargement des poids depuis {self.weights_path}...")
        try:
            from module1_urbanisme.pipeline.tinycd_models.change_classifier import ChangeClassifier
            self.model = ChangeClassifier(
                bkbn_name="efficientnet_b4",
                pretrained=False,
                output_layer_bkbn="3",
                freeze_backbone=False
            ).to(self.device)
            # Charger et adapter les poids (différence de nommage dans les couches mixing)
            # B32 CORRIGÉ : weights_only=True évite l'exécution de code arbitraire via pickle
            state_dict = torch.load(self.weights_path, map_location=self.device, weights_only=True)
            adapted_dict = {}
            remapped = 0
            for k, v in state_dict.items():
                new_k = k.replace('_mixing._convmix', '_convmix')
                if new_k != k:
                    remapped += 1
                adapted_dict[new_k] = v
            if remapped:
                logger.info(f"B32 : {remapped} clé(s) remappée(s) (_mixing._convmix → _convmix)")
            self.model.load_state_dict(adapted_dict, strict=False)
            self.model.eval()  # Mode inférence (désactive le Dropout/BatchNorm)
            logger.info("✅ Architecture Deep Learning (TinyCD) chargée avec succès et poids adaptés !")
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement de l'architecture PyTorch : {e}")

    def detect(self, t1_array: np.ndarray, t2_array: np.ndarray) -> np.ndarray:
        """
        Passe T1 et T2 dans le réseau de neurones et retourne le masque binaire.
        """
        if not self.is_ready or self.model is None:
            logger.error("🛑 Impossible de lancer l'inférence : Modèle non prêt.")
            return np.zeros(t1_array.shape[:2], dtype=np.uint8)

        import torch
        import cv2
        logger.info("🚀 Lancement de l'inférence Deep Learning PyTorch...")
        
        # Le modèle TinyCD s'attend en entrée à des tenseurs de shape (B, C, H, W).
        # Normalement il faut resize/crop les images à 256x256 et avoir 3 canaux (RGB).
        h, w = t1_array.shape[:2]
        
        try:
            # On utilise directement les 3 canaux (B04, B08, B11) passés en entrée !
            # t1_array et t2_array sont de forme (H, W, 3)
            
            # Numpy (H, W, C) -> PyTorch (C, H, W)
            # NORMALISATION DYNAMIQUE : garantir que l'IA reçoit des tenseurs [0.0, 1.0]
            max_val = max(t1_array.max(), t2_array.max())
            if max_val > 255.0:
                norm_factor = 10000.0  # Sentinel L2A standard uint16
            elif max_val > 2.0:
                norm_factor = 255.0    # 8-bit classique
            else:
                norm_factor = 1.0      # Déjà en réflectance float32
                
            tensor_t1 = torch.from_numpy(t1_array.transpose(2, 0, 1)).unsqueeze(0).float() / norm_factor
            tensor_t2 = torch.from_numpy(t2_array.transpose(2, 0, 1)).unsqueeze(0).float() / norm_factor
            
            # Normalisation Min-Max canal par canal (correcte pour données spectrales multi-bandes)
            # La normalisation ImageNet (RGB) est inadaptée à B04/B08/B11 Sentinel-2.
            # Cette version préserve les contrastes spectraux quel que soit le type de capteur.
            for c in range(tensor_t1.shape[1]):
                t1_c_min, t1_c_max = tensor_t1[:, c].min(), tensor_t1[:, c].max()
                t2_c_min, t2_c_max = tensor_t2[:, c].min(), tensor_t2[:, c].max()
                # Normalisation conjointe T1/T2 pour garder la comparabilité temporelle
                c_min = min(t1_c_min.item(), t2_c_min.item())
                c_max = max(t1_c_max.item(), t2_c_max.item())
                c_range = c_max - c_min + 1e-6
                tensor_t1[:, c] = (tensor_t1[:, c] - c_min) / c_range
                tensor_t2[:, c] = (tensor_t2[:, c] - c_min) / c_range
            
            # ── CORRECTIF MAJEUR : Résolution Native 10m/px ──────────────
            # AVANT : F.interpolate(256,256) écrasait la résolution spatiale et
            # forçait le modèle à voir 392x632 pixels dans 256x256 (bâtiments illisibles).
            # MAINTENANT : TinyCD (via EfficientNet) nécessite des entrées multiples de 32.
            # On pad l'image originale pour atteindre le multiple de 32 supérieur.
            import math
            import torch.nn.functional as F
            
            pad_h = (math.ceil(h / 32) * 32) - h
            pad_w = (math.ceil(w / 32) * 32) - w
            
            # Padding (left, right, top, bottom)
            if pad_h > 0 or pad_w > 0:
                tensor_t1 = F.pad(tensor_t1, (0, pad_w, 0, pad_h), mode='constant', value=0)
                tensor_t2 = F.pad(tensor_t2, (0, pad_w, 0, pad_h), mode='constant', value=0)

            tensor_t1, tensor_t2 = tensor_t1.to(self.device), tensor_t2.to(self.device)
            
            with torch.no_grad():
                output = self.model(tensor_t1, tensor_t2)
                # La sortie est de shape (1, 1, H_pad, W_pad)
                pred_mask = (output > TINYCD_CHANGE_THRESHOLD).squeeze().cpu().numpy().astype(np.uint8)
            
            # ── On supprime le padding pour revenir à la shape originale (H, W)
            if pad_h > 0 or pad_w > 0:
                pred_mask = pred_mask[:h, :w]
            # ─────────────────────────────────────────────────────────────
            
            return pred_mask
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'inférence PyTorch: {e}")
            return np.zeros((h, w), dtype=np.uint8)

