import numpy as np
import cv2
from sklearn.cluster import MiniBatchKMeans
import logging

logger = logging.getLogger(__name__)

class AIDetector:
    """
    Modèle d'Intelligence Artificielle non supervisé (Clustering K-Means + Vision par Ordinateur)
    Remplace le seuillage NDBI par une classification multispectrale intelligente.

    B39 — LIMITATION BI-TEMPORELLE :
      K-Means analyse T1 et T2 indépendamment. Les clusters ne sont pas comparables
      entre dates (le cluster 2 de T1 ≠ le cluster 2 de T2). Le pipeline compense en
      comparant les masques binaires finaux (bâti/non-bâti). Amélioration future :
      empiler T1+T2 en un seul array avant clustering pour obtenir des clusters cohérents.

    B40 — SCORING MATÉRIAUX LOCAUX :
      Le scoring intègre des pondérations adaptées aux matériaux de construction ivoiriens :
      - Tôle ondulée : SWIR/NDBI très élevé (0.25-0.40), texture forte (angles francs)
      - Béton brut : NDBI modéré (0.10-0.25), plus faible que béton peint européen
      - Terre battue (banco) : NDBI faible (0.10-0.20), similaire au sol nu latéritique
      Le paramètre texture est crucial pour distinguer banco (lisse) de tôle (arêtes vives).
    """
    def __init__(self, n_clusters=4):
        self.n_clusters = n_clusters

    def normalize(self, band):
        """Normalise une matrice entre 0 et 255 (format image)."""
        b_min, b_max = np.nanmin(band), np.nanmax(band)
        if b_max - b_min == 0:
            return np.zeros(band.shape, dtype=np.uint8)
        norm = (band - b_min) / (b_max - b_min) * 255.0
        return norm.astype(np.uint8)

    def compute_features(self, b04, b08, b11):
        """
        Extrait les "Features" (Caractéristiques) pour le modèle IA.
        Combine NDBI, NDVI, et une détection de contours (Texture).
        """
        # 1. Calculs Spectraux
        b04_f = b04.astype(np.float32)
        b08_f = b08.astype(np.float32)
        b11_f = b11.astype(np.float32)

        # NDBI (Eau/Nuages perturbent moins que bâti)
        ndbi = np.divide((b11_f - b08_f), (b11_f + b08_f), out=np.zeros_like(b11_f), where=(b11_f + b08_f) != 0)
        
        # NDVI (Végétation)
        ndvi = np.divide((b08_f - b04_f), (b08_f + b04_f), out=np.zeros_like(b04_f), where=(b08_f + b04_f) != 0)

        # 2. Texture par détection de contours (Filtre de Sobel)
        # Les bâtiments ont des angles forts, la terre nue non.
        b08_norm = self.normalize(b08)
        sobelx = cv2.Sobel(b08_norm, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(b08_norm, cv2.CV_64F, 0, 1, ksize=3)
        texture = np.sqrt(sobelx**2 + sobely**2)
        texture = texture / np.max(texture) if np.max(texture) > 0 else texture

        # Stacking des features (H, W, 3)
        features = np.dstack((ndbi, ndvi, texture))
        return features

    def predict_buildings(self, b04, b08, b11):
        """
        Applique un algorithme de Machine Learning (K-Means Clustering)
        pour isoler la classe "Bâti" des classes "Végétation", "Sol Nu", et "Eau".
        """
        logger.info("IA: Extraction des features Multispectrales et Structurelles...")
        features = self.compute_features(b04, b08, b11)
        h, w, c = features.shape
        
        # Préparation des données pour Scikit-Learn (1D array of 3D points)
        X = features.reshape((-1, 3))
        
        # Remplacer les NaN par 0
        X = np.nan_to_num(X)

        logger.info(f"IA: Entraînement du modèle K-Means ({self.n_clusters} clusters)...")
        kmeans = MiniBatchKMeans(n_clusters=self.n_clusters, random_state=42, batch_size=2048, n_init="auto")
        labels = kmeans.fit_predict(X)
        
        # Reconstruire l'image des classes
        segmented = labels.reshape((h, w))

        # Identifier le cluster appartenant aux bâtiments (NDBI élevé, NDVI très faible, Texture modérée à forte)
        centers = kmeans.cluster_centers_
        # centres = [NDBI, NDVI, Texture]
        
        # B40 : Score de "Bâti" adapté matériaux ivoiriens
        # NDBI × 1.2 (tôle ondulée = NDBI très élevé, discriminant principal)
        # - NDVI (exclure végétation)
        # + Texture × 0.7 (tôle = arêtes vives vs terre battue = lisse)
        scores = centers[:, 0] * 1.2 - centers[:, 1] + (centers[:, 2] * 0.7)  # type: ignore
        
        # BUG#3 CORRIGÉ : exclure les clusters qui ressemblent à de l'eau/lagune/bateaux
        # Un cluster eau a NDBI < -0.05 (eau ou métal très réfléchissant sur eau)
        # On pénalise lourdement les clusters qui seraient de l'eau pour éviter
        # que les bateaux du Port Bouët soient classés comme "Bâtiments"
        for k in range(len(centers)):
            if centers[k, 0] < -0.05:  # NDBI négatif = eau probable
                scores[k] = -999  # exclusion

        built_cluster_idx = np.argmax(scores)
        if scores[built_cluster_idx] == -999:
            # Tous les clusters ressemblent à de l'eau → retourner masque vide
            logger.warning("IA K-Means : aucun cluster bâti valide trouvé (image trop neigeuse/nuageuse/marine)")
            return np.zeros((b04.shape[0], b04.shape[1]), dtype=np.uint8), np.zeros_like(b04)
        
        # Masque binaire du bâti
        built_mask = (segmented == built_cluster_idx).astype(np.uint8)

        # Morphologie Mathématique (Filtre de nettoyage des pixels isolés)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        # Ouverture (Enlever le bruit)
        built_mask = cv2.morphologyEx(built_mask, cv2.MORPH_OPEN, kernel)
        # Fermeture (Boucher les trous dans les bâtiments)
        built_mask = cv2.morphologyEx(built_mask, cv2.MORPH_CLOSE, kernel)

        logger.info(f"IA: Cluster Bâti identifié (ID {built_cluster_idx}). Masque généré.")
        return built_mask, segmented

    def extract_clusters_regions(self, model_mask, min_size=2):
        """
        Utilise l'intelligence artificielle (Vision) pour extraire les polygones connectés.
        Remplace complètement la méthode de scipy.ndimage.label.
        """
        # Connected Components d'OpenCV est extrêmement rapide et précis
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(model_mask, connectivity=8)
        
        regions = []
        for i in range(1, num_labels): # Ignorer le background (0)
            size = stats[i, cv2.CC_STAT_AREA]
            if size >= min_size:
                cx, cy = centroids[i]
                regions.append({
                    "centroid": (int(cy), int(cx)), # (row, col)
                    "size_pixels": int(size)
                })
        
        return regions
