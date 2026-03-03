#!/usr/bin/env python3
"""
Script de diagnostic des erreurs 500
"""

import os
import sys
import subprocess
import json
import requests
from pathlib import Path

def diagnose_500_errors():
    """Diagnostic complet des erreurs 500"""
    print("🔍 DIAGNOSTIC DES ERREURS 500")
    print("="*50)
    
    # 1. Vérifier les logs du serveur Django
    print("\n1. Vérification des logs Django...")
    try:
        result = subprocess.run([
            "python", "manage.py", "shell", "-c", 
            "import logging; logging.basicConfig(level=logging.DEBUG); "
            "from django.test import Client; "
            "c = Client(); "
            "response = c.get('/'); "
            "print(f'Status: {response.status_code}'); "
            "if hasattr(response, 'content'): print(f'Content preview: {response.content[:200]}')"
        ], 
        capture_output=True, text=True, cwd=".")
        
        print(f"Sortie: {result.stdout}")
        if result.stderr:
            print(f"Erreurs: {result.stderr}")
            
    except Exception as e:
        print(f"Exception: {str(e)}")
    
    # 2. Test direct avec requests et capture des erreurs
    print("\n2. Test HTTP direct avec capture d'erreurs...")
    try:
        response = requests.get("http://127.0.0.1:8001/", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        if response.status_code == 500:
            print("ERREUR 500 DÉTECTÉE!")
            print("Content (premières lignes):")
            print(response.text[:1000])
    except requests.exceptions.RequestException as e:
        print(f"Erreur de requête: {str(e)}")
    
    # 3. Vérification de la configuration URLs
    print("\n3. Vérification configuration URLs...")
    try:
        result = subprocess.run([
            "python", "manage.py", "shell", "-c", 
            "from django.urls import get_resolver; "
            "from django.conf import settings; "
            "resolver = get_resolver(); "
            "try: match = resolver.resolve('/'); print(f'URL résolue: {match}'); "
            "except Exception as e: print(f'Erreur résolution URL: {e}')"
        ], 
        capture_output=True, text=True, cwd=".")
        
        print(f"Résolution URL: {result.stdout}")
        if result.stderr:
            print(f"Erreurs URL: {result.stderr}")
            
    except Exception as e:
        print(f"Exception URL: {str(e)}")
    
    # 4. Vérification des imports de views
    print("\n4. Vérification imports views...")
    try:
        result = subprocess.run([
            "python", "-c", 
            "from module1_urbanisme.views_web import dashboard; "
            "print('Import views_web OK')"
        ], 
        capture_output=True, text=True, cwd=".")
        
        print(f"Import views: {result.stdout}")
        if result.stderr:
            print(f"Erreurs import: {result.stderr}")
            
    except Exception as e:
        print(f"Exception import: {str(e)}")
    
    # 5. Vérification template dashboard
    print("\n5. Vérification template dashboard...")
    template_path = Path("templates/module1/dashboard.html")
    if template_path.exists():
        print(f"Template trouvé: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"Taille template: {len(content)} caractères")
            
            # Vérifier les erreurs communes
            if 'module1/dashboard.html' in content:
                print("✅ Template name correct")
            else:
                print("❌ Template name incorrect dans le contenu")
                
            # Vérifier la syntaxe Django
            django_tags = ['{% %}', '{{ }}', '{# #}', '{% if %}', '{% for %}']
            for tag in django_tags:
                count = content.count(tag)
                if count > 0:
                    print(f"Tag Django '{tag}': {count} occurrences")
    else:
        print("❌ Template non trouvé")
    
    print("\n" + "="*50)
    print("🏁 DIAGNOSTIC TERMINÉ")

if __name__ == "__main__":
    diagnose_500_errors()
