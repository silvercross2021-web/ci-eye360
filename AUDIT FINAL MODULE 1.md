# AUDIT FINAL TECHNIQUE — MODULE 1 (URBANISME)
## Projet CIV-Eye — Surveillance du Bâti par Satellite

Ce document constitue le rapport final d'audit technique du **Module 1** du projet CIV-Eye. Il explique de manière simplifiée comment le système détecte les constructions en Côte d'Ivoire.

---

### 1. Objectif du Module 1
Le Module 1 a pour mission de surveiller l'évolution urbaine (notamment à Treichville/Abidjan) en comparant des images satellites à différentes dates. Il identifie :
- Les **nouvelles constructions** (maisons, entrepôts).
- Les **démolitions** ou terrassements.
- La **conformité** vis-à-vis du cadastre (zones constructibles ou non).

---

### 2. Les Sources de Données (Les yeux du système)
Le système ne se contente pas d'une seule image. Il combine plusieurs sources :
- **Sentinel-2 (Optique) :** Des images gratuites de l'agence spatiale européenne (ESA) prises tous les 5 jours. Elles permettent de voir les couleurs et les matériaux au sol.
- **Sentinel-1 (Radar) :** Des ondes qui traversent les nuages. Très utile en saison des pluies pour confirmer la présence de béton/métal.
- **Google Open Buildings V3 & Microsoft Footprints :** Des bases de données mondiales qui listent les bâtiments déjà connus par IA.
- **Cadastre V10 :** La carte officielle des terrains de l'État pour savoir si une zone est autorisée à être bâtie.

---

### 3. Fonctionnement du Pipeline (Le cerveau du système)

Le processus de détection se déroule en **4 grandes étapes**, appelées "Couches de vérification".

#### Étape A : Le Calcul du Changement (NDBI)
Le système compare deux dates (Ex: Janvier 2024 vs Janvier 2025). 
- Il utilise un indice mathématique appelé **NDBI** (*Normalized Difference Built-up Index*). Cet indice fait ressortir le béton et les toitures en tôle.
- Si le score NDBI augmente fortement sur une zone, le système suspecte une nouvelle construction.

#### Étape B : La Vérification en 4 Couches
Pour éviter les erreurs (faux positifs), chaque détection doit passer 4 tests :
1. **Couche Bâtiment :** Est-ce que Google ou Microsoft connaissent déjà un bâtiment ici ?
2. **Couche Historique (T1) :** Est-ce qu'on voyait déjà du béton à la première date ? (Si oui, ce n'est pas "nouveau").
3. **Couche Actuelle (T2) :** Est-ce que le signal béton est bien présent et stable à la deuxième date ?
4. **Couche Légale (Cadastre) :** La zone est-elle "Habitable", "Industrielle" ou "Non-constructible" (Zone Rouge) ?

#### Étape C : L'Intelligence Artificielle (Le filtre de précision)
Deux modes d'IA sont disponibles pour affiner les résultats :
- **Mode K-Means (Standard) :** Une IA qui regroupe les pixels par ressemblance pour isoler les formes de bâtiments.
- **Mode Deep Learning (TinyCD) :** Un réseau de neurones sophistiqué (Expérimental) capable de reconnaître des structures complexes, même avec une résolution limitée.

#### Étape D : Élimination des Bruit (Masquages)
Le système nettoie automatiquement l'image :
- **Masque Eau (NDWI) :** Pour ne pas confondre un bateau sur la lagune avec une maison.
- **Masque Nuages (SCL) :** Pour ignorer les zones cachées par la météo.

---

### 4. Guide Technique des Fichiers Clés

| Fichier | Rôle Principal |
| :--- | :--- |
| `models.py` | Définit comment les données sont stockées dans la base (PostgreSQL/PostGIS). |
| `run_detection.py` | Le chef d'orchestre qui lance tout le processus. |
| `ndbi_calculator.py` | Le module qui fait les calculs mathématiques sur les images satellites. |
| `verification_4_couches.py` | La logique qui décide si une alerte est "Haute priorité" ou "Fausse alerte". |
| `sentinel_data_fetcher.py` | L'outil qui va chercher automatiquement les images sur internet (Sentinel Hub, CDSE, Microsoft). |

---

### 5. Conclusion de l'Audit
Le Module 1 est techniquement robuste et capable de fonctionner de manière autonome. Son architecture "multi-source" (Optique + Radar + IA) le rend particulièrement adapté au contexte ivoirien où la couverture nuageuse est fréquente.

**Points forts :** 100% automatisé, multi-source, respectueux des standards géographiques (WGS84/UTM).
**Points d'attention :** Nécessite une clé API GEE ou CDSE pour fonctionner à plein régime.

---
*Fin du rapport d'audit — 2026*
