import os
import urllib.request

# Créer le dossier pour héberger les poids
weights_dir = os.path.join("module1_urbanisme", "data_use", "weights")
os.makedirs(weights_dir, exist_ok=True)
print(f"Dossier {weights_dir} prêt pour recevoir le fichier tinycd.pth")
