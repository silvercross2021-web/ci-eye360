import subprocess
import os
import time

# Liste des scripts et commandes à exécuter dans l'ordre de l'audit chirurgical
PHASE_1_2_SCRIPTS = [
    "test_1_1_inventory.py",
    "test_1_2_dimensions.py",
    "test_1_3_crs.py",
    "test_1_4_black_pixels.py",
    "test_1_5_cloud_timeout.py",
    "test_1_6_tokens.py",
    "test_1_7_dates.py",
    "test_1_8_b03.py",
    "test_2_1_ndbi.py",
    "test_2_2_ndvi.py",
    "test_2_3_water.py",
    "test_2_4_bsi_stability.py",
    "test_2_5_kmeans.py",
    "test_2_6_normalisation.py"
]

PHASE_3_4_5_COMMANDS = [
    "audit_3_1", "audit_3_2", "audit_3_3", "audit_3_4", "audit_3_5",
    "audit_4_1", "audit_4_2", "audit_4_3", "audit_4_4", "audit_4_5",
    "audit_5_1", "audit_5_2", "audit_5_3", "audit_5_4", "audit_5_5",
    "audit_5_6", "audit_5_7", "audit_5_8"
]

def run_step(name, cmd_list):
    print(f"\n>>> DÉBUT : {name}")
    success_count = 0
    fail_count = 0
    
    for cmd in cmd_list:
        print(f"  Exécution de {cmd.split('.')[0]}...", end=" ", flush=True)
        try:
            full_cmd = ["python", f"test_speciale/{cmd}.py" if not cmd.endswith(".py") else f"test_speciale/{cmd}"]
            
            # Forcer l'encodage UTF-8 et ajouter le dossier racine au PYTHONPATH
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
            
            result = subprocess.run(
                full_cmd, 
                capture_output=True, 
                text=True, 
                timeout=60, 
                encoding='utf-8', 
                errors='ignore',
                env=env
            )
            
            # Un test est réussi s'il retourne le code 0 et si sa sortie contient un mot-clé de succès
            output = result.stdout + result.stderr
            keywords = ["Réussie", "SUCCESS", "validé", "Terminée", "effectuée", "Termin", "valide", "détectée", "stable", "✅", "Success", "RÉUSSIE", "VALIDÉ", "ALERTE", "⚠️"]
            is_success = (result.returncode == 0) and any(kw in output for kw in keywords)
            
            if is_success:
                print("✅ [OK]")
                success_count += 1
            else:
                print("❌ [ÉCHEC]")
                if result.stdout or result.stderr:
                    print(f"--- SORTIE ERREUR ---")
                    print(result.stdout)
                    print(result.stderr)
                    print(f"---------------------")
                fail_count += 1
        except Exception as e:
            print(f"🔥 ERREUR : {e}")
            fail_count += 1
    
    return success_count, fail_count

def main():
    start_time = time.time()
    print("====================================================")
    print("🩺 CIV-EYE : LANCEUR D'AUDIT CHIRURGICAL COMPLET")
    print("====================================================")
    
    s1, f1 = run_step("PHASE 1 & 2 : INTÉGRITÉ ET MATHS", PHASE_1_2_SCRIPTS)
    s2, f2 = run_step("PHASE 3, 4 & 5 : LOGIQUE MÉTIER", PHASE_3_4_5_COMMANDS)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "="*50)
    print(f"RÉSULTAT FINAL DE L'AUDIT :")
    print(f"  - TESTS RÉUSSIS   : {s1 + s2}")
    print(f"  - TESTS ÉCHOUÉS   : {f1 + f2}")
    print(f"  - TEMPS TOTAL     : {total_time:.1f} secondes")
    print("="*50)
    
    if (f1 + f2) == 0:
        print("\n✅ VOTRE PIPELINE EST 100% ROBUSTE ET PRÊT POUR LA DÉMO.")
    else:
        print("\n⚠️ CERTAINS TESTS ONT ÉCHOUÉ. VÉRIFIEZ LES LOGS DANS /logs/")

if __name__ == "__main__":
    main()
