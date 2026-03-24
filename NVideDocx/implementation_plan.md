# Plan d'implémentation — Phase 0 à Phase 2

## Contexte

Après audit complet de tous les fichiers, voici l'état réel du code :

### ✅ Déjà appliqués (ne pas retoucher)
| Correctif | Fichier | État |
|---|---|---|
| A1 — AABB Microsoft | [pipeline/verification_4_couches.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py) | ✅ Done |
| A2 — Shapely classification | [pipeline/verification_4_couches.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py) | ✅ Done |
| A3 — alert_level='veille' | [pipeline/verification_4_couches.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py) | ✅ Done |
| A4 — BSI formule B08 | [pipeline/ndbi_calculator.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py) | ✅ Done |
| A5 — chemins explicites | [pipeline/ndbi_calculator.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py) | ✅ Done |
| A6 — WGS84 géométries | [management/commands/run_detection.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/management/commands/run_detection.py) | ✅ Done |
| A7 — BBOX envelope | [management/commands/import_microsoft.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/management/commands/import_microsoft.py) | ✅ Done |
| A8 — chemins absolus | [management/commands/import_sentinel.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/management/commands/import_sentinel.py) | ✅ Done |
| A9 — Count import (commande) | [management/commands/import_cadastre.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/management/commands/import_cadastre.py) | ✅ Done |
| A10 — Dashboard compteur | [views_web.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/views_web.py) | ✅ Done |

### 🔴 Bug restant à corriger
| Bug | Fichier | Ligne |
|---|---|---|
| **A9-bis** — `models.Count` non résolu dans le **pipeline** | [pipeline/import_cadastre.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/import_cadastre.py) | L134 |

---

## Proposed Changes

### Phase 0 — Correction bug résiduel A9-bis

#### [MODIFY] [import_cadastre.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/import_cadastre.py)
- Ligne 134 : remplacer `models.Count('id')` → `Count('id')` (déjà importé ligne 10)

---

### Phase 1 — Améliorations logiques pipeline (L1 à L6)

#### [MODIFY] [ndbi_calculator.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py)

**L1** — [detect_changes()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#136-198) : ajouter détection démolitions :
```python
demolished = (ndbi_t1 > 0.25) & (ndbi_t2 < 0.05)
```
Retourner `'demolished'` dans le dict résultat et dans `'all_changes'`.

**L3** — [detect_changes()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#136-198) : ajouter masque NDVI optionnel :
```python
# Si ndvi_t2 fourni : filtrer les faux positifs végétation
if ndvi_t2 is not None:
    vegetation_mask = (ndvi_t2 > 0.4)
    new_constructions = new_constructions & ~vegetation_mask
```

**L4** — [extract_change_regions()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#202-270) : ajuster min_size par défaut à 2 (bâtiment ~20m²) et ajouter max_size=500.

**L5** — Nouvelle méthode `compute_confidence(ndbi_t1, ndbi_t2, bsi, surface_px, cloud_cover_pct)` : score dynamique 0.0–1.0.

**L6** — Nouvelle méthode `apply_scl_mask(array, scl_path)` : masque nuages/ombres via fichier SCL (classes 3, 8, 9, 10).

#### [MODIFY] [verification_4_couches.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py)

**L1** — Ajouter type `'demolition'` dans [_is_valid_change()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py#150-168) et [_classify_by_zoning()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py#173-244).
**L2** — Masque eau : dans [_is_valid_change()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/verification_4_couches.py#150-168), si SCL classe 6 détectée → ignorer.

#### [MODIFY] [run_detection.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/management/commands/run_detection.py)

- [extract_change_regions()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#202-270) : extraire aussi les régions `demolished` si présentes dans les résultats
- `--min-region-size` : changer défaut de `10` à `2`
- Passer le SCL path à `apply_scl_mask()` avant le calcul NDBI si disponible

---

### Phase 2 — Indices spectraux NDVI et BUI

#### [MODIFY] [ndbi_calculator.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py)

Ajouter 3 méthodes :
- `calculate_ndvi(b04_path, b08_path)` → [(B08-B04)/(B08+B04)](file:///c:/Users/silve/Desktop/SIADE_hackathon/tests/test_pipeline_validation.py#41-43) avec résample si besoin
- `calculate_bui(ndbi, ndvi)` → `clip(ndbi - ndvi, -1, 1)` en numpy
- [detect_changes()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#136-198) : accepter `ndvi_t2` optionnel pour activer le masque végétation et le filtre BUI

---

## Verification Plan

### Tests automatiques
Le fichier [tests/test_pipeline_validation.py](file:///c:/Users/silve/Desktop/SIADE_hackathon/tests/test_pipeline_validation.py) existant sera enrichi et ré-exécuté.

**Commande de lancement** (depuis la racine du projet) :
```powershell
cd c:\Users\silve\Desktop\SIADE_hackathon
python tests/test_pipeline_validation.py
```

Tests ajoutés dans ce fichier :
- **TEST 8** — `calculate_ndvi()` : vérifie que NDVI ∈ [-1, 1] et que pixels végétation > 0.4 sont cohérents
- **TEST 9** — `calculate_bui()` : vérifie BUI = NDBI - NDVI
- **TEST 10** — [detect_changes()](file:///c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/pipeline/ndbi_calculator.py#136-198) avec NDVI : vérifie que le masque végétation réduit les faux positifs
- **TEST 11** — démolitions : vérifie la présence de `'demolished'` dans le dict résultat
- **TEST 12** — `apply_scl_mask()` : vérifie que les classes SCL 8/9/10 produisent NaN

### Vérification du bug A9-bis
```powershell
cd c:\Users\silve\Desktop\SIADE_hackathon
python -c "from module1_urbanisme.pipeline.import_cadastre import Command; print('OK')"
```
