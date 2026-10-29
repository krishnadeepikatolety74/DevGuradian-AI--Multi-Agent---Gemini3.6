"""
DevGuardian AI — ClaimWise AI Root Dispatcher
Allows running ClaimWise AI from the DevGuardian AI root directory:
    python claimwiseai.py

This automatically executes the project from its actual workspace:
    generated_projects/ClaimWise_AI/claimwiseai.py
using its actual workspace directory as cwd and port 5003.
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CANDIDATE_DIRS = [
    ROOT_DIR / "generated_projects" / "ClaimWise_AI",
    ROOT_DIR / "generated_projects" / "ClaimWiseAI",
    ROOT_DIR / "generated_projects" / "proj_87ec37b85e",
]

PROJECT_DIR = None
for c in CANDIDATE_DIRS:
    if c.exists() and (c / "claimwiseai.py").exists():
        PROJECT_DIR = c.resolve()
        break

if not PROJECT_DIR:
    try:
        import sqlite3
        db_path = ROOT_DIR / "instance" / "devguardian.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_path FROM projects WHERE name LIKE '%ClaimWise%' OR id = 'proj_87ec37b85e'")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] and Path(row[0]).exists():
                PROJECT_DIR = Path(row[0]).resolve()
    except Exception:
        pass

if not PROJECT_DIR or not (PROJECT_DIR / "claimwiseai.py").exists():
    print("Error: Could not locate ClaimWise AI workspace or claimwiseai.py entry point.")
    sys.exit(1)

port = os.environ.get("PORT", "5003")
env = os.environ.copy()
env["PORT"] = str(port)
env["PYTHONPATH"] = str(PROJECT_DIR)
env["PYTHONUNBUFFERED"] = "1"

print("\n==========================================================")
print(" DevGuardian AI — Launching Independent Generated Project")
print(" Project: ClaimWise AI")
print(f" Working Directory: {PROJECT_DIR}")
print(" Entry Point: claimwiseai.py")
print(f" Assigned Port: {port}")
print(f" Local URL: http://127.0.0.1:{port}")
print("==========================================================\n")

cmd = [sys.executable, "claimwiseai.py"] + sys.argv[1:]
try:
    proc = subprocess.run(cmd, cwd=str(PROJECT_DIR), env=env)
    sys.exit(proc.returncode)
except KeyboardInterrupt:
    print("\nClaimWise AI stopped.")
    sys.exit(0)
