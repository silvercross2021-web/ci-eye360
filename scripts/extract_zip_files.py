#!/usr/bin/env python3
import zipfile
import os
import sys
from pathlib import Path

def extract_zip_with_sanitized_names(zip_path, extract_to):
    """
    Extrait un fichier ZIP en remplaçant les ':' par des '-' dans les noms de fichiers
    pour éviter les erreurs Windows (0x80070057)
    """
    try:
        # Créer le dossier d'extraction s'il n'existe pas
        os.makedirs(extract_to, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                # Remplacer les ':' par des '-' dans le nom de fichier
                original_name = file_info.filename
                sanitized_name = original_name.replace(':', '-')
                
                # Créer le chemin complet du fichier extrait
                extract_path = os.path.join(extract_to, sanitized_name)
                
                # Si c'est un répertoire, créer le répertoire
                if file_info.is_dir():
                    os.makedirs(extract_path, exist_ok=True)
                    print(f"Créé répertoire: {extract_path}")
                else:
                    # S'assurer que le répertoire parent existe
                    parent_dir = os.path.dirname(extract_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    
                    # Extraire le fichier avec le nom modifié
                    with zip_ref.open(file_info) as source, open(extract_path, 'wb') as target:
                        target.write(source.read())
                    
                    print(f"Extrait: {original_name} -> {sanitized_name}")
        
        print(f"\n✅ Extraction réussie de {zip_path} vers {extract_to}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction de {zip_path}: {e}")
        return False

def main():
    # Chemins des fichiers ZIP
    base_dir = Path("c:/Users/silve/Desktop/SIADE_hackathon/module1_urbanisme/data_use")
    
    zip_files = [
        base_dir / "T1.zip",
        base_dir / "T2.zip"
    ]
    
    # Dossier de destination
    extract_dir = base_dir / "sentinel"
    
    print("🚀 Début de l'extraction des fichiers ZIP...")
    print(f"Dossier de destination: {extract_dir}")
    print("-" * 50)
    
    success_count = 0
    
    for zip_file in zip_files:
        if zip_file.exists():
            print(f"\n📦 Traitement de: {zip_file.name}")
            if extract_zip_with_sanitized_names(zip_file, extract_dir):
                success_count += 1
        else:
            print(f"❌ Fichier introuvable: {zip_file}")
    
    print("-" * 50)
    print(f"📊 Résultat: {success_count}/{len(zip_files)} fichiers extraits avec succès")
    
    if success_count == len(zip_files):
        print("🎉 Tous les fichiers ont été extraits correctement!")
    else:
        print("⚠️ Certains fichiers n'ont pas pu être extraits.")

if __name__ == "__main__":
    main()
