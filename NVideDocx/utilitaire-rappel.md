# 📘 Guide Utilitaire et Rappel d'Installation (CIV-Eye)

Ce document sert d'**aide-mémoire exhaustif** regroupant la configuration, les clés d'API, les limites d'accès (qui expirent bientôt) et la procédure complète pour tout réinstaller ou renouveler de zéro sans rien casser.

---

## 🏗️ 1. Architecture du Pipeline (Ce que nous avons construit)

Pour ne pas utiliser les fichiers `.tiff` manuellement, nous avons automatisé 100% de la chaîne d'acquisition :
1. **Phase 1 & 2** : Amélioration du calculateur NDBI (Nuages, Démolitions, Indice NDVI, BUI).
2. **Phase 3 (`sentinel_data_fetcher.py`)** : Acquisition automatique des bandes satellitaires prêtes pour numpy (via Sentinel Hub ou Copernicus).
3. **Phase 4 (`gee_composite.py`)** : Compilation ultra-précise de plusieurs images sur la saison sèche (Novembre → Mars) pour éliminer les nuages de manière absolue via Google Earth Engine (GEE).

---

## ⏳ 2. Gestion des Expirations et Renouvellement des APIs

C'est le point crucial : tu utilises actuellement des accès gratuits/essais qui peuvent expirer dans 10 à 30 jours. Voici comment les renouveler sans perdre de temps.

### A. Sentinel Hub API (Phase 3)
* **État actuel** : Tu utilises un compte d'essai (Trial) qui te donne de gros quotas pour le développement. **Il expirera sous peu.**
* **Impact si expiré** : Le script ne pourra plus se connecter et basculera automatiquement sur l'API publique de secours (CDSE Copernicus) qui est plus lente.
* **Comment renouveler (Procédure de secours)** :
  1. Va sur [shapps.sentinel-hub.com](https://shapps.sentinel-hub.com).
  2. Déconnecte-toi et **crée un nouveau compte** avec une nouvelle adresse email.
  3. Une fois connecté, retourne dans le menu de gauche : **User Settings** (ou **OAuth Clients**).
  4. Clique sur **"+ New OAuth Client"**.
  5. Copie le **Client ID** et le **Client Secret**.
  6. Ouvre le fichier `.env` de ton projet et **remplace** les anciennes valeurs :
     ```env
     SENTINEL_HUB_CLIENT_ID="<NOUVEAU_ID>"
     SENTINEL_HUB_CLIENT_SECRET="<NOUVEAU_SECRET>"
     ```

### B. Google Earth Engine (GEE) (Phase 4)
* **État actuel** : Tu as enregistré le projet `apt-momentum-490804-r7` (My Project 3854) pour un usage Non-Commercial (Académique).
* **Impact si expiré/bloqué** : Google ne suspend généralement pas les comptes académiques en 10 jours, mais le "Token" local de ton PC peut expirer toutes les quelques semaines pour des raisons de sécurité.
* **Comment Rafraîchir ton accès (Erreur "Credentials", "Token Expired" ou "403 Forbidden")** :
  1. Si tu as juste une erreur terminale un matin, ouvre PowerShell dans le projet et tape :
     ```powershell
     earthengine authenticate --force
     ```
  2. Reconnecte-toi avec ton compte Google sur la page qui s'ouvre, autorise tout et copie le code. Colle-le dans le terminal.
* **Que faire si ton projet Cloud est supprimé / banni ?** :
  1. Va sur Google Cloud Console et crée un **nouveau projet**.
  2. Note le champ `ID du projet` (ex: `nouveau-projet-123`).
  3. Va sur [cette page](https://console.cloud.google.com/earth-engine/configuration) en sélectionnant ton nouveau projet.
  4. Enregistre-le pour une utilisation "Non commerciale".
  5. Mets à jour ton `.env` : `GEE_PROJECT_ID="nouveau-projet-123"`.
  6. Refais un `earthengine authenticate --force`.

### C. La Roue de Secours Absolue (CDSE Copernicus)
* Si les deux du dessus (Sentinel Hub et GEE) meurent en pleine journée de hackathon ou d'évaluation... Pas de panique !
* J'ai codé l'Option B dans `sentinel_data_fetcher.py`. C'est **Copernicus Data Space Ecosystem (CDSE)**.
* **Avantage** : C'est un service public européen. C'est 100% gratuit, sans inscription, sans clé API. Le pipeline basculera automatiquement dessus si les clés du `.env` foirent. C'est juste un peu moins rapide.

---

## 🛠️ 3. Fichiers et Dossiers Vitaux (Anti-Panique)

Au cas où tu dois re-cloner le projet sur un autre PC, ne perds surtout pas :

- Le **Fichier `.env`** (À la racine du projet). Ce fichier n'est jamais poussé sur GitHub (à cause du `.gitignore`). Si tu changes de PC, tu **dois** créer manuellement un fichier `.env` textuel et y remettre tes clés.
- `module1_urbanisme/pipeline/sentinel_data_fetcher.py` (Générateur des tableaux numpy Sentinel)
- `module1_urbanisme/pipeline/gee_composite.py` (Générateur des masques sans nuages Google Earth Engine)

---

## 💻 4. Commandes Systèmes Fréquentes

**Pour relancer le pipeline complet de zéro (Import API + Détection) :**

1. Ouvre le shell Django pour nettoyer la BDD :
   ```powershell
   python manage.py shell -c "from module1_urbanisme.models import DetectionConstruction, ImageSatellite; DetectionConstruction.objects.all().delete(); ImageSatellite.objects.all().delete(); print('Reset OK')"
   ```
2. Import automatique des images depuis le Cloud (Phase 3 & 4) :
   ```powershell
   $env:PYTHONUTF8=1
   python manage.py import_sentinel_api --date 2024-01-29
   python manage.py import_sentinel_api --date 2025-01-13
   ```
3. Lancement de la détection (Phase 1 & 2) :
   ```powershell
   $env:PYTHONUTF8=1
   python manage.py run_detection
   ```

**Pour diagnostiquer l'état exact des APIs sur une nouvelle machine :**
Nous avons gardé les scripts à la racine, tu peux créer :
```powershell
python test_sh.py    # Teste Sentinel Hub
python test_gee.py   # Teste Google Earth Engine
```
*(C'est la première chose à faire si tu changes d'ordinateur !)*

---

*L'infrastructure Data est bétonnée. Ce fichier est là pour rassurer ton esprit. L'accès aux données satellitaires survivra au hackathon.*
