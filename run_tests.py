#!/usr/bin/env python3
"""
CIV-EYE — Lanceur de tous les tests
=====================================

Lance l'intégralité des suites de tests et affiche les résultats de façon
lisible dans le terminal. Chaque ligne [OK]/[WARN]/[FAIL] est comptabilisée.

Usage :
  python run_tests.py              (toutes les suites)
  python run_tests.py --fast       (suites rapides seulement, sans DB_REAL et PIPE_REAL)
  python run_tests.py ENV DB PIPE  (suites nommées seulement)

Suites disponibles :
  ENV        Variables d'environnement, dépendances Python
  DB         Modèles Django, ORM, serializers
  DB_REAL    Intégrité des données réelles en base (images, zones, footprints)
  PIPE       Pipeline numérique (NDBI, AI, détection — sans BDD)
  PIPE_REAL  Pipeline sur vraies données Sentinel-2
  API        Endpoints REST DRF
  WEB        Vues Django (dashboard, détections, zones)
  CMD        Management commands (import, export, pipeline_check)
  ROB        Robustesse et cas limites
  CIV        Contexte ivoirien Treichville (BBOX, seuils, indices)
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(ROOT_DIR, "test_special")

PYTHON = sys.executable

ALL_SUITES = ["ENV", "DB", "DB_REAL", "PIPE", "PIPE_REAL", "API", "WEB", "CMD", "ROB", "CIV"]
FAST_SUITES = ["ENV", "DB", "PIPE", "API", "WEB", "CMD", "ROB", "CIV"]

# Indicateurs visuels
C_OK    = "  [OK]  "
C_WARN  = "  [WARN]"
C_FAIL  = "  [FAIL]"
C_INFO  = "  [INFO]"

SEP     = "=" * 72
SEP_LGT = "-" * 72
SEP_MID = "·" * 72


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def print_banner():
    print()
    print(SEP)
    print("  CIV-EYE MODULE 1 — LANCEUR DE TESTS COMPLET")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  Racine : {ROOT_DIR}")
    print(SEP)

def print_suite_header(suite_name):
    print()
    print(SEP)
    print(f"  SUITE : {suite_name}")
    print(SEP)

def print_suite_footer(suite_name, nb_ok, nb_warn, nb_fail, elapsed):
    print(SEP_LGT)
    status = "ECHEC" if nb_fail > 0 else ("AVERTISSEMENT" if nb_warn > 0 else "SUCCES")
    marker = "[FAIL]" if nb_fail > 0 else ("[WARN]" if nb_warn > 0 else "[OK]  ")
    print(f"  {marker} {suite_name:<12} | OK={nb_ok:>3}  WARN={nb_warn:>3}  FAIL={nb_fail:>3} | {elapsed:.1f}s")

def count_line(line):
    """Retourne ('OK'|'WARN'|'FAIL'|None, line). Vérification sur la ligne brute."""
    # Les tests affichent '  [OK]   ...' ou '  [WARN] ...' ou '  [FAIL] ...'
    # On teste sur line (non strippé) pour conserver les espaces de tête.
    if "  [OK]" in line or "[OK]  " in line:
        return "OK", line
    if "  [WARN]" in line or "[WARN]" in line:
        return "WARN", line
    if "  [FAIL]" in line or "[FAIL]" in line:
        # Exclure les lignes de résumé footer (ex: '[FAIL] DB  | ...')
        # pour ne pas doubler le comptage
        if "| OK=" in line:
            return None, line
        return "FAIL", line
    return None, line


# ─────────────────────────────────────────────────────────────────────────────
# RUN UNE SUITE
# ─────────────────────────────────────────────────────────────────────────────

def run_suite(suite_name):
    script = os.path.join(TEST_DIR, f"test_{suite_name}.py")
    if not os.path.exists(script):
        print(f"  [FAIL] Script introuvable : {script}")
        return 0, 0, 1, 0.0

    print_suite_header(suite_name)

    nb_ok = nb_warn = nb_fail = 0
    t0 = time.time()

    try:
        proc = subprocess.Popen(
            [PYTHON, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=ROOT_DIR,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            kind, _ = count_line(line)
            if kind == "OK":
                nb_ok += 1
            elif kind == "WARN":
                nb_warn += 1
            elif kind == "FAIL":
                nb_fail += 1
            # Afficher chaque ligne immédiatement
            print(line)

        proc.wait()

        # Si le process s'est terminé avec un code != 0 sans FAIL explicite,
        # compter comme 1 FAIL pour signaler le problème
        if proc.returncode != 0 and nb_fail == 0:
            print(f"  [FAIL] {suite_name} s'est terminé avec code {proc.returncode} (erreur non capturée)")
            nb_fail += 1

    except Exception as e:
        print(f"  [FAIL] Erreur lors de l'exécution de {suite_name}: {e}")
        nb_fail += 1

    elapsed = time.time() - t0
    print_suite_footer(suite_name, nb_ok, nb_warn, nb_fail, elapsed)
    return nb_ok, nb_warn, nb_fail, elapsed


# ─────────────────────────────────────────────────────────────────────────────
# RÉSUMÉ GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

def print_grand_total(results, total_elapsed):
    print()
    print(SEP)
    print("  RÉSUMÉ GLOBAL — TOUTES SUITES")
    print(SEP)
    print(f"  {'SUITE':<14} {'OK':>5}  {'WARN':>5}  {'FAIL':>5}  {'TEMPS':>6}")
    print(SEP_MID)

    total_ok = total_warn = total_fail = 0
    suites_failed = []

    for suite, ok, warn, fail, elapsed in results:
        marker = " [FAIL]" if fail > 0 else (" [WARN]" if warn > 0 else " [OK]  ")
        print(f"  {marker} {suite:<10} {ok:>5}  {warn:>5}  {fail:>5}  {elapsed:>5.1f}s")
        total_ok   += ok
        total_warn += warn
        total_fail += fail
        if fail > 0:
            suites_failed.append(suite)

    print(SEP_MID)
    print(f"  {'TOTAL':<14} {total_ok:>5}  {total_warn:>5}  {total_fail:>5}  {total_elapsed:>5.1f}s")
    print()

    if total_fail == 0 and total_warn == 0:
        print("  [OK]   SYSTEME 100% OPERATIONNEL — Aucun echec, aucun avertissement.")
    elif total_fail == 0:
        print(f"  [WARN] {total_warn} avertissement(s) \u2014 aucun echec critique. Systeme fonctionnel.")
    else:
        print(f"  [FAIL] {total_fail} echec(s) dans : {', '.join(suites_failed)}")
        print("         Consulter les lignes [FAIL] ci-dessus pour corriger.")

    print()
    print(SEP)
    print()
    return total_fail == 0


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # Choisir les suites à lancer
    if "--fast" in args:
        suites = FAST_SUITES
        args.remove("--fast")
    elif args:
        # Les suites sont passées en argument (ex: python run_tests.py ENV DB PIPE)
        requested = [a.upper() for a in args]
        invalid = [s for s in requested if s not in ALL_SUITES]
        if invalid:
            print(f"[FAIL] Suites inconnues : {invalid}")
            print(f"       Disponibles : {ALL_SUITES}")
            sys.exit(1)
        suites = requested
    else:
        suites = ALL_SUITES

    print_banner()
    print(f"  Suites sélectionnées : {suites}")
    print(f"  Fichiers tests dans  : {TEST_DIR}")
    print()

    t_global = time.time()
    results = []

    for suite in suites:
        ok, warn, fail, elapsed = run_suite(suite)
        results.append((suite, ok, warn, fail, elapsed))

    total_elapsed = time.time() - t_global
    success = print_grand_total(results, total_elapsed)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
