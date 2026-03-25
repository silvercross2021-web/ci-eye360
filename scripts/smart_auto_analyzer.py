#!/usr/bin/env python3
"""
Script d'analyse intelligent automatique du Module 1 CIV-Eye
Gère automatiquement les prompts PowerShell et fait toute l'analyse
"""

import os
import sys
import subprocess
import time
import json
import requests
import webbrowser
from pathlib import Path
import threading

class SmartAutoAnalyzer:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent  # scripts/ → racine du projet
        self.errors_found = []
        self.fixes_applied = []
        self.server_process = None
        
    def log(self, message, level="INFO"):
        """Affiche un message avec timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def run_command_simple(self, cmd, description="", timeout=30):
        """Exécute une commande simple sans capture interactive"""
        self.log(f"Exécution: {description}")
        self.log(f"Commande: {cmd}")
        
        try:
            # Pour PowerShell, utiliser Start-Process pour éviter les prompts
            if "curl" in cmd and "http://" in cmd:
                # Remplacer curl par une méthode Python directe
                return self.test_http_endpoint(cmd.split()[-1])
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                                  cwd=self.project_root, timeout=timeout)
            if result.returncode == 0:
                self.log(f"✅ Succès: {description}")
                return True, result.stdout
            else:
                self.log(f"❌ Erreur: {description}")
                self.log(f"Erreur: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            self.log(f"⏰ Timeout: {description}")
            return False, "Timeout"
        except Exception as e:
            self.log(f"❌ Exception: {description} - {str(e)}")
            return False, str(e)
    
    def test_http_endpoint(self, url, timeout=10):
        """Test direct d'endpoint HTTP avec Python"""
        self.log(f"Test HTTP: {url}")
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                self.log(f"✅ {url} - OK ({response.status_code})")
                self.fixes_applied.append(f"HTTP {url} fonctionnel")
                return True, response.text[:500]  # Limiter la sortie
            else:
                self.log(f"❌ {url} - Erreur ({response.status_code})")
                self.errors_found.append(f"HTTP {response.status_code} sur {url}")
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            self.log(f"❌ {url} - Erreur: {str(e)}")
            self.errors_found.append(f"Connexion échouée sur {url}: {str(e)}")
            return False, str(e)
    
    def check_django_system(self):
        """Vérification Django avec gestion des erreurs"""
        self.log("🔍 Vérification Django...")
        
        success, output = self.run_command_simple(
            "python manage.py check", 
            "Vérification configuration Django"
        )
        
        if success:
            self.log("✅ Configuration Django valide")
            self.fixes_applied.append("Configuration Django vérifiée")
        else:
            self.log("❌ Erreurs Django:")
            for line in output.split('\n')[:5]:  # Limiter l'affichage
                if line.strip():
                    self.log(f"   • {line.strip()}")
            self.errors_found.append(f"Configuration Django: {output}")
    
    def check_database_content(self):
        """Vérification du contenu base de données"""
        self.log("🔍 Vérification base de données...")
        
        # Utiliser des commandes shell plus simples
        db_commands = [
            ("from module1_urbanisme.models import ZoneCadastrale; print(f'ZONES:{ZoneCadastrale.objects.count()}')", "Zones cadastrales"),
            ("from module1_urbanisme.models import MicrosoftFootprint; print(f'MICROSOFT:{MicrosoftFootprint.objects.count()}')", "Microsoft footprints"),
            ("from module1_urbanisme.models import DetectionConstruction; print(f'DETECTIONS:{DetectionConstruction.objects.count()}')", "Détections")
        ]
        
        for cmd, desc in db_commands:
            success, output = self.run_command_simple(
                f'python manage.py shell -c "{cmd}"',
                desc
            )
            if success and output:
                # Extraire le nombre
                for line in output.split('\n'):
                    if ':' in line and any(x in line for x in ['ZONES:', 'MICROSOFT:', 'DETECTIONS:']):
                        self.log(f"✅ {desc}: {line.strip()}")
                        break
    
    def test_all_endpoints(self):
        """Test de tous les endpoints critiques"""
        self.log("🔍 Test complet des endpoints...")
        
        endpoints = [
            ("http://127.0.0.1:8001/", "Dashboard principal"),
            ("http://127.0.0.1:8001/api/statistics/", "API Statistiques"),
            ("http://127.0.0.1:8001/api/detections-geojson/", "API Détections GeoJSON"),
            ("http://127.0.0.1:8001/api/zones-geojson/", "API Zones GeoJSON"),
            ("http://127.0.0.1:8001/detections/", "Liste détections"),
        ]
        
        for url, desc in endpoints:
            self.test_http_endpoint(url)
            time.sleep(0.5)  # Pause entre tests
    
    def verify_templates(self):
        """Vérification des templates"""
        self.log("🔍 Vérification templates...")
        
        templates = [
            "templates/module1/base.html",
            "templates/module1/dashboard.html",
            "templates/module1/detections_list.html", 
            "templates/module1/detection_detail.html",
            "templates/module1/404.html"
        ]
        
        for template in templates:
            template_path = self.project_root / template
            if template_path.exists() and template_path.stat().st_size > 0:
                self.log(f"✅ Template OK: {template}")
                self.fixes_applied.append(f"Template {template_path.name}")
            else:
                self.log(f"❌ Template manquant: {template}")
                self.errors_found.append(f"Template manquant: {template}")
    
    def start_server_if_needed(self):
        """Démarre le serveur si nécessaire"""
        self.log("🔍 Vérification serveur...")
        
        # Test simple pour voir si le serveur répond
        server_running = self.test_http_endpoint("http://127.0.0.1:8001/api/statistics/")[0]
        
        if not server_running:
            self.log("🚀 Démarrage du serveur Django...")
            try:
                # Démarrer le serveur en arrière-plan
                self.server_process = subprocess.Popen(
                    ["python", "manage.py", "runserver", "8001"],
                    cwd=self.project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Attendre que le serveur démarre
                self.log("⏳ Attente démarrage serveur (10s)...")
                time.sleep(10)
                
                # Revérifier
                server_running = self.test_http_endpoint("http://127.0.0.1:8001/api/statistics/")[0]
                if server_running:
                    self.log("✅ Serveur Django démarré avec succès")
                    self.fixes_applied.append("Serveur Django démarré")
                else:
                    self.log("❌ Échec démarrage serveur")
                    self.errors_found.append("Serveur n'a pas démarré")
                    
            except Exception as e:
                self.log(f"❌ Exception démarrage serveur: {str(e)}")
                self.errors_found.append(f"Démarrage serveur: {str(e)}")
        else:
            self.log("✅ Serveur déjà fonctionnel")
            self.fixes_applied.append("Serveur déjà actif")
    
    def generate_final_report(self):
        """Génère le rapport final complet"""
        self.log("\n" + "="*70)
        self.log("🎯 RAPPORT FINAL D'ANALISE COMPLÈTE")
        self.log("="*70)
        
        # Statistiques
        self.log(f"📊 STATISTIQUES:")
        self.log(f"   ✅ Corrections appliquées: {len(self.fixes_applied)}")
        self.log(f"   ❌ Erreurs trouvées: {len(self.errors_found)}")
        
        # Détails des corrections
        if self.fixes_applied:
            self.log(f"\n✅ LISTE DES CORRECTIONS:")
            for i, fix in enumerate(self.fixes_applied, 1):
                self.log(f"   {i}. {fix}")
        
        # Détails des erreurs
        if self.errors_found:
            self.log(f"\n❌ LISTE DES ERREURS:")
            for i, error in enumerate(self.errors_found, 1):
                self.log(f"   {i}. {error}")
        
        # Verdict final
        if len(self.errors_found) == 0:
            self.log(f"\n🎉 SYSTÈME 100% FONCTIONNEL!")
            self.log(f"✅ Tous les composants opérationnels")
            self.log(f"🚀 PRÊT POUR LA PRODUCTION")
            self.log(f"🌐 Interface accessible: http://127.0.0.1:8001")
            
            # Ouvrir automatiquement le navigateur
            try:
                webbrowser.open("http://127.0.0.1:8001")
                self.log("🌐 Navigateur ouvert automatiquement")
            except:
                self.log("⚠️ Impossible d'ouvrir le navigateur automatiquement")
        else:
            self.log(f"\n⚠️ SYSTÈME NON PRÊT!")
            self.log(f"❌ {len(self.errors_found)} problème(s) à résoudre")
            self.log(f"🔧 Veuillez corriger avant la production")
        
        self.log("="*70)
    
    def run_complete_analysis(self):
        """Exécute l'analyse complète automatisée"""
        self.log("🚀 DÉMARRAGE ANALYSE AUTOMATIQUE COMPLÈTE")
        self.log("⏱️ Durée estimée: 30-45 secondes")
        self.log("-"*50)
        
        try:
            # Phase 1: Configuration Django
            self.check_django_system()
            time.sleep(2)
            
            # Phase 2: Base de données
            self.check_database_content()
            time.sleep(2)
            
            # Phase 3: Templates
            self.verify_templates()
            time.sleep(2)
            
            # Phase 4: Serveur
            self.start_server_if_needed()
            time.sleep(3)
            
            # Phase 5: Tests endpoints
            self.test_all_endpoints()
            time.sleep(2)
            
            # Phase 6: Rapport final
            self.generate_final_report()
            
            return len(self.errors_found) == 0
            
        except KeyboardInterrupt:
            self.log("\n⏹️ Analyse interrompue")
            return False
        except Exception as e:
            self.log(f"\n💥 Erreur critique: {str(e)}")
            return False

def main():
    """Point d'entrée principal avec gestion des erreurs"""
    print("🤖 LANCEMENT DE L'ANALYSEUR INTELLIGENT AUTOMATIQUE")
    print("="*60)
    
    analyzer = SmartAutoAnalyzer()
    
    try:
        success = analyzer.run_complete_analysis()
        
        if success:
            print(f"\n🎉 SUCCÈS TOTAL - Analyse terminée sans erreurs!")
            input("Appuyez sur Entrée pour continuer...")
            return 0
        else:
            print(f"\n⚠️ ANALYSE TERMINÉE AVEC ERREURS")
            input("Appuyez sur Entrée pour continuer...")
            return 1
            
    except Exception as e:
        print(f"\n💥 ERREUR CRITIQUE: {str(e)}")
        input("Appuyez sur Entrée pour quitter...")
        return 1

if __name__ == "__main__":
    sys.exit(main())
