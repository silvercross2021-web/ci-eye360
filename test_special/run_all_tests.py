"""
Runner global — exécute tous les tests test_special/ et produit un résumé.
"""
import os, sys, subprocess, json

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TEST_DIR)

SUITES = ["test_ENV", "test_DB", "test_DB_REAL", "test_PIPE", "test_PIPE_REAL", "test_API", "test_WEB", "test_CMD", "test_ROB", "test_CIV"]

GLOBAL = {"OK": 0, "WARN": 0, "FAIL": 0}

print("=" * 70)
print("  CIV-EYE — SUITE DE TESTS SPÉCIAUX")
print("=" * 70)

for suite in SUITES:
    script = os.path.join(TEST_DIR, f"{suite}.py")
    print(f"\n{'='*70}")
    print(f"  SUITE : {suite}")
    print(f"{'='*70}")
    result = subprocess.run(
        [sys.executable, script],
        cwd=ROOT_DIR,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  >>> {suite} a retourné code {result.returncode}")

print("\n" + "=" * 70)
print("  FIN DES TESTS")
print("=" * 70)
