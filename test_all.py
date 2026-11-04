"""Run every offline test. Exit code 1 if any fail. Run: python test_all.py"""
import subprocess
import sys
from pathlib import Path

bad = []
for t in sorted(Path(".").glob("test_*.py")):
    if t.name == "test_all.py":
        continue
    r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {t.name}")
    if r.returncode:
        bad.append(t.name)
        print(r.stderr[-1500:])
print("all passed" if not bad else f"FAILED: {bad}")
sys.exit(bool(bad))
