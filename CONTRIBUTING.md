# 🛑 GUIDE DE CONTRIBUTION & RÈGLES GIT (À LIRE IMPÉRATIVEMENT) 🛑

Bienvenue dans l'équipe de développement de **CIV-EYE** ! 
Afin que la collaboration à 3 sur les 3 modules différents se passe de manière fluide et sans conflits destructeurs, **nous avons mis en place des règles strictes de gestion de version (Git)**.

Si vous travaillez sur le Module 2 (Agroécologie) ou le Module 3 (Orpaillage), vous devez suivre ce guide à la lettre pour éviter d'écraser le travail du Module 1 ou de casser le système de base.

---

## 🏗️ 1. RÈGLE D'OR : SÉPARATION DES MODULES
**Chaque développeur est responsable de son propre module.**
*   **Ne touchez JAMAIS** aux dossiers des autres modules (ex: si vous êtes sur le M2, n'ouvrez pas `module1_urbanisme/` ou `module3_orpaillage/`).
*   **Ne modifiez pas l'interface globale ou le paramétrage lourd sans accord :** Si vous devez modifier `config/settings.py` (pour ajouter votre application), le faire proprement. 
*   **Design Global :** Le fichier `templates/module1/base.html` contient le "Cyber-Design" sombre. Si vous créez vos interfaces, étendez cette base plutôt que de recréer du style. Et ne la modifiez pas sous peine de casser le Dashboard de toute l'application.

---

## 🌿 2. NOMENCLATURE DES BRANCHES (BRANCHING MODEL)
**Ne travaillez JAMAIS directement sur la branche `main` ou `master` !**
Chaque nouvelle tâche doit avoir sa propre branche. La nomenclature doit être la suivante :

*   Pour une nouvelle fonctionnalité : `feature/nom-du-module-votre-tache`
    *   *Exemple : `feature/module2-integration-cartes-ndwi`*
*   Pour corriger un bug : `bugfix/nom-du-module-le-bug`
    *   *Exemple : `bugfix/module3-correction-upload-images`*

---

## 🛠️ 3. LE WORKFLOW PARFAIT (ÉTAPE PAR ÉTAPE)

### A. Avant de commencer à coder (Tous les matins)
Toujours s'assurer d'avoir la dernière version du travail des autres :
```bash
git checkout main
git pull origin main
```

### B. Créer sa branche de travail
À partir de la branche `main` fraîchement mise à jour, créez votre branche :
```bash
git checkout -b feature/module2-analyse-vegetation
```

### C. Développer et Sauvegarder (Commits)
Faites des petits commits réguliers et clairs. Un seul gros commit "Update" est interdit.
```bash
git add module2_agroecologie/models.py
git commit -m "feat(mod2): Création du modèle pour l'indice NDVI"
```

### D. Pousser son code sur GitHub
Une fois votre fonctionnalité terminée (et testée en local !) :
```bash
git push -u origin feature/module2-analyse-vegetation
```

### E. Le Merge (Fusion)
**Ne fusionnez PAS vous-même vers `main` en ligne de commande.**
1. Allez sur GitHub.
2. Créez une **Pull Request (PR)** de votre branche vers `main`.
3. Informez l'équipe. Quelqu'un d'autre doit approuver rapidement la PR avant de cliquer sur "Merge".

---

## ⚠️ 4. CE QU'IL NE FAUT ABSOLUMENT PAS FAIRE !
❌ **Faire un `git push -f` (Force push) sur le main :** C'est le meilleur moyen de supprimer définitivement le code des autres.
❌ **Commiter vos bases de données ou clés secrètes :** Assurez-vous que le `db.sqlite3`, le dossier virtuel `venv/` et les fichiers `.env` soient bien ignorés.
❌ **Faire des migrations de base de données en conflit :** Si vous touchez à vos `models.py`, générez vos migrations (`python manage.py makemigrations nom_du_module`) et commitez ce fichier de migration. NE MODIFIEZ PAS les migrations des autres.
❌ **Écraser les `requirements.txt` :** Si vous installez une nouvelle librairie (ex: `pip install librosa`), ajoutez-la proprement à la fin du `requirements.txt` (`pip freeze > requirements.txt` écraserait la mise en page propre actuelle).

## 💡 5. NORMES TECHNIQUES (PIPELINE & IA)
Pour garantir la précision des détections du Module 1 :
*   **Indices Spectraux :** Toute modification de `ndbi_calculator.py` doit être validée par un test unitaire (`tests.py`).
*   **Modèles IA :** Les nouveaux poids de modèles (PyTorch/Sklearn) doivent être placés dans `module1_urbanisme/data_use/weights/`. Ne jamais commiter de fichiers `.pth` > 50Mo (utiliser Git LFS si nécessaire).
*   **Données Satellitaires :** Toujours privilégier les fonctions de `sentinel_data_fetcher.py` pour l'acquisition afin de maintenir la compatibilité multi-source.

## 💡 6. ASTUCE : GÉRER LES CONFLITS "MERGE CONFLICTS"
Si GitHub vous annonce qu'il ne peut pas fusionner automatiquement car quelqu'un a touché au même fichier que vous :
1. Sur votre branche : `git pull origin main`
2. Ouvrez le fichier en conflit dans votre éditeur (VSCode).
3. Résolvez le conflit proprement.
4. `git add le_fichier` puis `git commit -m "fix: résolution de conflit"`
5. Relancez le `git push`.
