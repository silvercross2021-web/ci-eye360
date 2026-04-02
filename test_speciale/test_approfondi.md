🛰️ PROTOCOLE D'AUDIT TOTAL — MODULE 1 CIV-EYE
📂 PHASE 1 : ACQUISITION & INTÉGRITÉ (La Source)
Objectif : Garanti 100% de fiabilité sur l'image disque.

Action 1.1 : Inventaire Spatial
Vérifier la présence des fichiers B04.tif, B08.tif, B11.tif et SCL.tif pour T1 et T2.
Action 1.2 : Audit des Dimensions
Utiliser rasterio pour vérifier : Largeur(px) x Hauteur(px) identiques sur TOUTES les bandes (T1=T2).
Action 1.3 : Audit de Projection (CRS)
Vérifier que tout est en EPSG:4326 (WGS84). Si une image est en UTM, le crash est garanti.
Action 1.4 : Scanner de Pixels Noirs
Calculer le pourcentage de pixels à 0 (vides) sur les bords de l'image.
Action 1.5 : Test de Lecture Cloud
Simuler une déconnexion internet pendant l'appel API CDSE pour voir si le timeout est bien géré.
Action 1.6 : Test du Token
Vérifier si le fichier .env a des identifiants valides ou si on est en mode "Anonyme" CDSE.
Action 1.7 : Contrôle de Date
Comparer la date du nom de fichier avec les métadonnées internes du TIFF (ex: PROPERTY_ACQUISITION_DATE).
Action 1.8 : Test B03 (Synthèse)
Relouer le calcul du B03_downloader.py et vérifier si l'image générée n'est pas toute noire.
🧪 PHASE 2 : LOGIQUE MATHÉMATIQUE (Les Indices)
Objectif : Valider la précision spectrale au pixel près.

Action 2.1 : Stress-Test NDBI
Prendre un pixel avec B08=100 et B11=100. Calcul : (100-100)/(100+100) = 0. Est-ce que le code gère le 0/0 ?
Action 2.2 : Audit NDVI (Végétation)
Vérifier que les valeurs NDVI sont bien entre -1 et 1. Enregistrer toute valeur hors-norme.
Action 2.3 : Audit NDWI (Eau)
Identifier la lagune Ébrié sur la carte. Les valeurs doivent être négatives. Si elles sont positives, le masque est inversé !
Action 2.4 : Test de Stabilité BSI
Comparer le BSI entre T1 et T2 sur une zone de forêt dense. Le BSI ne doit pas bouger.
Action 2.5 : Audit K-Means Central
Extraire les coordonnes des 3 "centroïdes" (moyennes de classes). Un centroïde "Bâti" doit avoir un NDBI > 0.1.
Action 2.6 : Test de Normalisation
Vérifier si les données sont bien remises à l'échelle [0,1] avant d'être envoyées au K-Means.
🧩 PHASE 3 : FUSION & VÉRIFICATION GOOGLE (Le Nettoyage)
Objectif : Valider le mariage Flou/Net et l'historique V1/V3.

Action 3.1 : Test de l'Intersection V1
Prendre 10 bâtiments de la V1. Vérifier s'ils sont bien soustraits du masque de détection 2025.
Action 3.2 : Audit Géométrique V3
Lancer un calcul de Surface de Recouvrement. Si un point Sentinel touche un bâtiment Google V3, quelle est la surface commune ? (Seuil 70% attendu).
Action 3.3 : Test du Buffer (La Marge)
Vérifier si le buffer de 10m (1 pixel) ne "mange" pas les bâtiments voisins.
Action 3.4 : Audit de la Base de Données MicrosoftFootprint
Compter le nombre de bâtiments Google V3 importés dans ta zone Treichville. S'il y en a < 100, l'import a échoué.
Action 3.5 : Test de Re-projection à la volée
Transformer une coordonnée Pixel(x,y) en coordonnée GPS(Lat,Lon) et vérifier sur Google Maps.
🛡️ PHASE 4 : LES 4 COUCHES DE SÉCURITÉ (Le Filtrage)
Objectif : Prouver la robustesse contre les faux positifs.

Action 4.1 : Test Couche 1 (Nuages SCL)
Prendre un pixel classé "Cloud" (valeur 8 ou 9 en SCL). Vérifier qu'il est ignoré à 100%.
Action 4.2 : Test Couche 2 (Végétation NDVI)
Sur une zone de mangrove (lagune), vérifier que le NDVI élevé bloque la détection de bâtiment.
Action 4.3 : Test Couche 3 (Sol Nu BSI)
Prendre un terrain de sport (Terre battue). Le BSI sera positif mais le NDBI faible. Est-ce que le code fait la différence ?
Action 4.4 : Test Couche 4 (Eau NDWI)
Vérifier si un navire métallique (très brillant au radar/optique) est éliminé car il "flotte" sur un pixel d'eau.
Action 4.5 : Audit du Score de Confiance
Simuler un cas : Optique=0.8, Radar=0.2. Le score final doit être modulé (ex: 0.45). Calculer cette valeur ligne par ligne.
⚖️ PHASE 5 : CADASTRE & ALERTE (Le Verdict Légal)
Objectif : Valider la conformité administrative.

Action 5.1 : Test de la "Zone Rouge"
Identifier la zone de recul du canal. Placer une fausse détection dedans. Vérifier si elle sort en Alerte ROUGE (infraction).
Action 5.2 : Audit du Zonage
Vérifier le fichier ZoneCadastrale. Chaque zone a-t-elle un type_usage valide ?
Action 5.3 : Test de Classification
Si une détection est en zone industrielle, sort-elle bien en Alerte VERTE (autorisé) ?
Action 5.4 : Test Double-Comptage
Relancer le pipeline. Vérifier que la base de données ne crée pas de doublons mais "met à jour" l'existant.