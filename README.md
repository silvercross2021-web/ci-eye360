# CIV-EYE COMMAND CENTER 🛰️

## Système de Surveillance Spatiale de la Côte d'Ivoire
**Projet SIADE Hackathon** - Module 1 : Conformité Urbanistique et Cadastre

Bienvenue dans le dépôt central de l'application CIV-EYE. Cette plateforme permet l'analyse algorithmique des images satellitaires (Sentinel/Microsoft) couplées aux données cadastrales, pour déceler l'évolution de la construction sauvage.

---

🚨 **ATTENTION CO-ÉQUIPIERS** 🚨
**Avant de pusher la moindre ligne de code**, vous devez **IMPÉRATIVEMENT** lire le fichier [CONTRIBUTING.md](./CONTRIBUTING.md) pour les règles Git (Nomenclature des branches, séparation des modules, politique de push/merge). Le non-respect de ces règles peut écraser le travail des autres modules.

---
### 📂 Structure du Répertoire (Clean Repository)

```text
CIV-EYE/
│
├── config/                 # Configurations centrales Django (URLs, settings, base)
├── core/                   # Utilitaires globaux de l'application
├── data/                   # Fichiers bruts de données SIG (Si nécessaire localement)
├── docs/                   # 📚 Documentation système complète (.pdf, .docx, Plans)
├── exports/                # 💾 Fichiers exportés via le tableau de bord (Ex: GPS csv)
├── logs/                   # 📜 Logs de debug et erreurs d'exécution des scripts
├── media/                  # Images satellitaires natives et rasters téléchargés
├── module1_urbanisme/      # 🏗️ [MODULE 1] Logique métier de la conformité du Cadastre
├── module2_agroecologie/   # 🌱 [MODULE 2] (Dépendance Future) Agriculture / Végétation
├── module3_orpaillage/     # ⛏️ [MODULE 3] (Dépendance Future) Orpaillage clandestin
├── scripts/                # 🛠️ Outils, extracteurs et correctifs automatisés
├── static/                 # CSS/JS compilés, fonts, icônes
├── templates/              # 🎨 Design HTML (Thème "Cyber Tactique")
├── tests/                  # 🧪 Tests Unitaires et Validation du Pipeline
│
├── manage.py               # Exécutable natif Django
├── requirements.txt        # 📦 Liste complète et lockée des dépendances 
└── README.md               # Le présent fichier d'aide
```

---

### 🚀 Guide d'Installation Rapide

1. **Cloner le projet :**
```bash
git clone https://votre-repo/civ-eye.git
cd civ-eye
```

2. **Créer l'environnement virtuel et installer les dépendances :**
```bash
python -m venv venv
.\venv\Scripts\activate   # ou source venv/bin/activate sur Mac/Linux
pip install -r requirements.txt
```

3. **Migrations et initialisation :**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Lancement du Centre de Commande (Serveur) :**
```bash
python manage.py runserver 8080
```

*Naviguez ensuite vers `http://127.0.0.1:8080/` pour accéder au tableau de bord.*

---

### 🛠️ Scripts Annexes Disponibles
Pour l'administration, consulter le dossier `scripts/` :
- `export_detections_gps.py` : Exporte les centroïdes en clair dans un tableur (trouvable ensuite dans `exports/`).
- `smart_auto_analyzer.py` : Intelligence artificielle asynchrone pour la validation des géométries manquantes.
- `diagnose_500_errors.py` : Moteur de tracking d'erreur en cas de surcharge des requêtes HTTP.

> **Note de conception :** Le template "World Monitor" utilise l'empreinte graphique "Dark Mode / Cyber". Ne pas écraser les variables `:root` CSS dans le fichier `base.html` sous peine de briser la visibilité des matrices radar !
