"""
Runs every backend test script and prints one summary line per script.
Run from the backend folder:  python tests/run_all.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    "test_fsm.py",
    "test_phase1.py",
    "test_phase2.py",
    "test_evaluation.py",
    "test_legacy_migration.py",
    "test_accounts.py",
    "test_setup.py",
    "test_incidents.py",
    "test_desktop.py",
]

failed = []
for name in SUITES:
    proc = subprocess.run([sys.executable, os.path.join(HERE, name)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = proc.stdout + proc.stderr
    match = re.search(r"(\d+)/(\d+) checks passed", output)
    summary = f"{match.group(1)}/{match.group(2)}" if match else "no summary"
    ok = proc.returncode == 0 and match is not None and match.group(1) == match.group(2)
    print(f"{'PASS' if ok else 'FAIL'}  {name:<26} {summary}")
    if not ok:
        failed.append(name)

print("\nAll suites passed." if not failed else f"\nFailed: {', '.join(failed)}")
sys.exit(1 if failed else 0)
