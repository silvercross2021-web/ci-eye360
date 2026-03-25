# CONTRIBUTING — Guide de Contribution CIV-EYE

Ce guide explique comment contribuer au projet sans casser le travail des autres. **À lire avant de toucher au code.**

---

## 1. Séparation des modules

Chaque développeur est responsable de son propre module.

| Module | Dossier | Règle |
|---|---|---|
| Module 1 — Urbanisme | `module1_urbanisme/` | Ne pas modifier sans accord |
| Module 2 — Agroécologie | `module2_agroecologie/` | Responsable M2 uniquement |
| Module 3 — Orpaillage | `module3_orpaillage/` | Responsable M3 uniquement |

**Fichiers partagés à ne modifier qu'avec accord de l'équipe :**
- `config/settings.py` — configuration globale
- `config/urls.py` — routes globales
- `requirements.txt` — dépendances communes
- `templates/module1/base.html` — design "Cyber Tactique" partagé (ne pas réécrire le CSS `:root`)

---

## 2. Nomenclature des branches Git

Ne jamais travailler directement sur `main`.

```
feature/module1-nom-de-la-fonctionnalite
feature/module2-nom-de-la-fonctionnalite
bugfix/module1-description-du-bug
hotfix/description-urgente
```

**Exemples :**
```
feature/module2-integration-ndwi
bugfix/module1-correction-dates-detection
```

---

## 3. Workflow Git complet

### Étape 1 — Récupérer les dernières modifications (chaque matin)

```bash
git checkout main
git pull origin main
```

### Étape 2 — Créer sa branche

```bash
git checkout -b feature/module2-analyse-vegetation
```

### Étape 3 — Commiter régulièrement (petits commits clairs)

```bash
git add module2_agroecologie/models.py
git commit -m "feat(mod2): ajout modèle NDVI avec zone géographique"
```

Format des messages de commit :
- `feat(mod1):` — nouvelle fonctionnalité
- `fix(mod1):` — correction de bug
- `docs:` — documentation uniquement
- `test:` — ajout ou correction de tests
- `refactor:` — refactorisation sans changement de comportement

### Étape 4 — Pousser sa branche

```bash
git push -u origin feature/module2-analyse-vegetation
```

### Étape 5 — Créer une Pull Request (PR)

1. Aller sur GitHub → **New Pull Request**
2. Base : `main` ← Compare : votre branche
3. Décrire ce que vous avez fait
4. Informer l'équipe — **un autre développeur doit approuver avant de fusionner**

---

## 4. Ce qu'il ne faut jamais faire

❌ `git push -f` sur `main` — supprime le code des autres de façon irréversible

❌ Commiter `.env`, `db.sqlite3` ou `venv/` — ces fichiers sont dans `.gitignore`, vérifiez avant chaque push

❌ Faire `pip freeze > requirements.txt` — écrase la mise en forme actuelle. À la place, ajouter manuellement la ligne à la fin du fichier

❌ Modifier les migrations des autres modules — si vous changez un `models.py`, créez vos propres migrations :
```bash
python manage.py makemigrations module2_agroecologie
```

❌ Commiter des fichiers `.pth` (poids PyTorch) supérieurs à 50 Mo — utiliser Git LFS ou fournir un lien de téléchargement externe

---

## 5. Normes techniques

### Module 1 (pipeline existant)

- Toute modification de `ndbi_calculator.py` doit être accompagnée d'un test unitaire dans `module1_urbanisme/tests.py`
- Pour l'acquisition satellite, utiliser exclusivement `sentinel_data_fetcher.py` — il gère la priorité multi-source (CDSE → Sentinel Hub → Planetary Computer)
- Les poids de modèles IA vont dans `module1_urbanisme/data_use/weights/`
- Les images Sentinel TIF vont dans `module1_urbanisme/data_use/sentinel_api_exports/{date}/`

### Modules 2 et 3 (à développer)

- Créer vos propres modèles dans `module2_agroecologie/models.py` / `module3_orpaillage/models.py`
- Enregistrer votre module dans `config/settings.py` section `INSTALLED_APPS`
- Brancher vos URLs dans `config/urls.py` sous un préfixe dédié (`api/v2/` est réservé à Module 1)
- Étendre `templates/module1/base.html` pour l'interface (ne pas le modifier)

### Vérification avant chaque Push

```bash
python manage.py check          # 0 erreur Django obligatoire
python manage.py test module1_urbanisme   # tests M1 doivent passer
```

---

## 6. Résoudre un conflit Git

Quand GitHub indique "This branch has conflicts" :

```bash
# Sur votre branche de travail
git pull origin main

# Ouvrir les fichiers en conflit dans VSCode
# Résoudre les blocs <<< === >>> manuellement
# Puis :
git add fichier_corrige.py
git commit -m "fix: résolution conflit avec main"
git push
```

---

## 7. Documentation du projet

Avant de contribuer, lire les documents suivants :

| Fichier | Contenu |
|---|---|
| [README.md](./README.md) | Installation, commandes, structure du projet |
| [AUDIT FINAL MODULE 1.md](./AUDIT%20FINAL%20MODULE%201.md) | Fonctionnement simplifié du pipeline (non-technique) |
| [analyse_complet_1.F.md](./analyse_complet_1.F.md) | Audit technique complet — chaque fichier expliqué, tous les bugs connus et corrections appliquées |

`analyse_complet_1.F.md` est la référence technique principale. Il documente l'état exact du code, les choix d'architecture, et les limitations connues.
