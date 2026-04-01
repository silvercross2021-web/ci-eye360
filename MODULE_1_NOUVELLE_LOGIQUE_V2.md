# 🛰️ CIV-EYE Module 1 — Architecture Data Fusion (V2.0)

Ce document décrit la transition majeure entre la première approche purement Optique (V1.0) et la nouvelle architecture hybride de type *Data Fusion Optique/Radar* (V2.0) pour la détection urbaine de pointe.

---

## 🛑 1. Le Problème Initial (Ce qui n'allait pas avant)

Dans l'ancienne logique, le flux de détection fonctionnait ainsi :
1. **L'Optique seule décide** : Le système téléchargeait deux images **Sentinel-2** (Optique) et confiait l'analyse à une IA de comparaison d'image (TinyCD) accompagnée d'indices spectraux (NDBI, BSI).
2. **Le piège des Faux Positifs ("Doute Optique")** : Sentinel-2 est sensible aux conditions de surface. Un parking fraîchement bitumé, un embouteillage monstre avec le soleil qui se reflète sur les toits des voitures, du sable blanc sur les chantiers : **l'optique le voit briller et croit que c'est une nouvelle construction**.
3. **Le Radar bloqué** : Le script Radar (Sentinel-1) existait, mais c'était une "coquille vide" (un mock). Il attendait une clé API payante et très chère (*Sentinel Hub Enterprise*) pour fonctionner. Le code passait littéralement le Radar sous silence (`try... except... pass`).

**Conséquence :** La base de données affichait **556 détections**, dont beaucoup de "bruits" (routes, parkings, variations saisonnières) qui polluaient la lecture du cadastre.

---

## 🚀 2. La Nouvelle Logique (V2.0) : Data Fusion & Tolérance Zéro

Pour résoudre ces problèmes de manière professionnelle, fiable et *gratuite*, nous avons repensé entièrement l'architecture du Moteur.

### A. Intégration de Google Earth Engine (Le nouveau Radar Gratuit)
Plutôt que d'attendre une API payante, le système se connecte au cloud de calcul de Google (GEE).
* **Filtre Anti-Bruit :** L'API calcule en temps réel et côté serveurs Google une "Image Médiane" Sentinel-1 sur 30 jours pour annuler totalement l'effet de neige (Speckle) typique des radars.
* **La grandeur mesurée :** Ce qu'on télécharge n'est pas une "photo", mais la mesure physique de `Δ VV` (Différence de Backscatter). En clair : **Le volume vertical et sa densité métallique**.

### B. Le Tribunal : Juge Optique vs Juge Radar
Désormais, lors de l'extraction (`run_detection.py`), les deux signaux fusionnent :
L'Optique propose un suspect, le Radar confirme ou détruit l'accusation.

1. **Cas 1 — Accord Mutuel (Sur-Confiance)**
   * *Optique* : "C'est du ciment brillant."
   * *Radar* : "Le signal VV a bondi (≥ 2.0 dB), il y a un mur géométrique et/ou du métal."
   * *Résultat* : **Score de confiance boosté (+50%).** Validé.
2. **Cas 2 — Tolérance Zéro (L'Effet Parking)**
   * *Optique* : "C'est du béton tout neuf."
   * *Radar* : "Le signal VV n'a pas bougé (≤ 0 dB) ou s'est écroulé. La surface est **TOTALEMENT PLATE**."
   * *Résultat* : **L'alerte est purement et simplement SUPPRIMÉE de la liste.** La base de données reste saine, le parking/le goudron ne sont jamais dénoncés comme des habitations.
3. **Cas 3 — Perçage de Nuages**
   * *Optique* : "L'image est couverte de nuages (>20%), je ne suis pas sûr."
   * *Radar* : "Je passe à travers les nuages. Il y a un bâtiment majeur en dessous (+3.0 dB) !"
   * *Résultat* : **Confiance multipliée par deux.** L'alerte ressort gagnante.

### C. Filtre Spatial des Infrastructures (Anti-Ponts)
Dans la V1, l'algorithme "voyait" faussement des constructions sur les ponts d'Abidjan à cause de la variation du trafic (beaucoup de bagnoles = pic NDBI + pic Radar Métallique).
Dans la V2, un masque de "Geofencing" (`verification_4_couches.py`) a été hard-codé. **La boîte englobante des Ponts Houphouët-Boigny, De Gaulle, et HKB exclut systématiquement tout faux positif sur la lagune.** 

---

## 📊 3. Les Modifications du Dashboard (UI)

Cette nouvelle précision est valorisée sur le panneau de contrôle :
1. **Nettoyage Automatisé :** Le nombre de détections globales est drastiquement réduit (Passage de **556** à **341** pour Treichville), ne laissant émerger que **la Vérité Terrain confirmée en double aveugle**.
2. **Filtres Avancés :** Un nouveau filtre chirurgical "Confiance" ( % ) a été intégré. En cliquant dessus, l'utilisateur peut occulter les doutes persistants pour ne laisser flasher sur la carte que les infractions dont l'IA est certaine à **`≥ 90%`**, **`≥ 75%`** ou **`≥ 50%`**.

---

## Conclusion
Le **Module 1** n'est plus un POC (Proof-of-Concept) approximatif. Il possède maintenant des fondations algorithmiques capables de résister aux conditions réelles du terrain ivoirien, comme n'importe quel logiciel commercial de Remote Sensing.
