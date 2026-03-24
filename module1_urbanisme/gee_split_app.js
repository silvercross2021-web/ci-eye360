// CIV-EYE : Script Google Earth Engine App (Split-screen Comparison)
// Déployer ce script sur code.earthengine.google.com et créer une "App" publique.

// 1. Paramètres récupérés depuis l'URL (si appel via iframe)
var urlParams = ui.url.get('lat');
var lat = urlParams ? parseFloat(ui.url.get('lat')) : 5.305;
var lon = urlParams ? parseFloat(ui.url.get('lon')) : -4.015;

// 2. Définition de la Zone d'Intérêt (Abidjan) autour du point cliqué
var pt = ee.Geometry.Point([lon, lat]);
Map.centerObject(pt, 16); // Zoom max centré sur la détection

// 3. Récupération des images Sentinel-2 (Harmonized) pour T1 et T2
function getCloudFreeImage(year) {
  var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(pt)
    .filterDate(year + '-01-01', year + '-03-31') // Saison sèche
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20));
  
  // Masque nuage (SCL)
  return collection.map(function(img) {
    var scl = img.select('SCL');
    return img.updateMask(scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)));
  }).median(); // Image composite parfaite
}

var imageT1 = getCloudFreeImage(2024);
var imageT2 = getCloudFreeImage(2025);

// 4. Paramètres de visualisation RGB True Color
var visParams = {
  bands: ['B4', 'B3', 'B2'],
  min: 0,
  max: 3000,
  gamma: 1.4
};

// 5. Interface UI (Split Panel)
var leftMap = ui.Map();
var rightMap = ui.Map();

leftMap.addLayer(imageT1, visParams, 'Sentinel-2 (2024)');
rightMap.addLayer(imageT2, visParams, 'Sentinel-2 (2025)');

// Sync maps
var linker = ui.Map.Linker([leftMap, rightMap]);

// Marker rouge sur la détection ciblée
var marker = ui.Map.Layer(pt, {color: 'FF0000'}, 'Alerte CIV-Eye');
leftMap.layers().add(marker);
rightMap.layers().add(marker);

// Ajout des titres
leftMap.add(ui.Label('T1 : Janvier 2024', {position: 'bottom-left', fontWeight: 'bold'}));
rightMap.add(ui.Label('T2 : Janvier 2025', {position: 'bottom-right', fontWeight: 'bold'}));

var splitPanel = ui.SplitPanel({
  firstPanel: linker.get(0),
  secondPanel: linker.get(1),
  orientation: 'horizontal',
  wipe: true,
  style: {stretch: 'both'}
});

leftMap.setCenter(lon, lat, 17);
ui.root.widgets().reset([splitPanel]);
